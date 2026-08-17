from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from agentpost.config import Settings
from agentpost.control.models import (
    ApprovalDecision,
    ApprovalRequest,
    HumanActionAudit,
)
from agentpost.db import Database
from agentpost.main import create_app
from agentpost.messaging.models import Message

ADMIN_KEY = "admin-secret-admin-secret-admin-secret"


def _client(settings: Settings, database: Database) -> TestClient:
    protected = Settings(
        environment="test",
        database_url=settings.database_url,
        storage_path=settings.storage_path,
        api_key_pepper="test-agent-pepper",
        human_api_key_pepper="test-human-pepper",
        cursor_secret="test-cursor-secret",
        registration_token="register-secret",
        admin_token=ADMIN_KEY,
        human_confirmation_ttl_seconds=300,
        approval_default_ttl_seconds=86_400,
        log_level="WARNING",
    )
    return TestClient(create_app(settings=protected, database=database))


def _admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {ADMIN_KEY}"}


def _create_agent(client: TestClient, address: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/agents",
        headers={"X-Registration-Token": "register-secret"},
        json={
            "address": address,
            "display_name": address.partition("@")[0].title(),
            "capabilities": ["document-analysis"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_human(client: TestClient, email: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/admin/humans",
        headers=_admin_headers(),
        json={"email": email, "display_name": email.partition("@")[0]},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _grant(
    client: TestClient,
    *,
    human: dict[str, Any],
    agent: dict[str, Any],
    role: str,
) -> None:
    response = client.put(
        f"/api/v1/admin/humans/{human['user']['id']}/agents/{agent['agent']['id']}",
        headers=_admin_headers(),
        json={"role": role},
    )
    assert response.status_code == 200, response.text


def _agent_headers(agent: dict[str, Any], *, key: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {agent['api_key']}"}
    if key is not None:
        headers["Idempotency-Key"] = key
    return headers


def _approval_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "action_type": "publish.report",
        "summary": "发布季度银行研究报告",
        "justification": "需要面向获授权客户发布已完成的研究材料",
        "risk_level": "high",
        "payload": {"report_id": "report-2026-q3", "channel": "client_portal"},
    }
    payload.update(overrides)
    return payload


def _request_approval(
    client: TestClient,
    agent: dict[str, Any],
    *,
    key: str,
    payload: dict[str, Any] | None = None,
):
    return client.post(
        "/api/v1/approval-requests",
        headers=_agent_headers(agent, key=key),
        json=payload or _approval_payload(),
    )


def _login(client: TestClient, human: dict[str, Any]) -> str:
    response = client.post(
        "/api/v1/orbit/session",
        headers={"Authorization": f"Bearer {human['access_key']}"},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["csrf_token"])


def _confirmation(
    client: TestClient,
    human: dict[str, Any],
    approval_id: str,
    csrf_token: str,
    *,
    intent: str = "approve",
):
    return client.post(
        f"/api/v1/orbit/approval-requests/{approval_id}/confirmation",
        headers={
            "Authorization": f"Bearer {human['access_key']}",
            "X-CSRF-Token": csrf_token,
        },
        json={"intent": intent},
    )


def _decide(
    client: TestClient,
    approval_id: str,
    csrf_token: str,
    confirmation_token: str,
    *,
    key: str = "human-decision-1",
    decision: str = "approved",
    note: str = "已核对范围与接收人，可以发布。",
):
    return client.post(
        f"/api/v1/orbit/approval-requests/{approval_id}/decision",
        headers={
            "X-CSRF-Token": csrf_token,
            "X-Human-Confirmation": confirmation_token,
            "Idempotency-Key": key,
        },
        json={"decision": decision, "note": note},
    )


def test_owner_approves_with_csrf_reauthentication_and_single_use_confirmation(
    settings: Settings,
    database: Database,
) -> None:
    with _client(settings, database) as client:
        agent = _create_agent(client, "research@agents.local")
        owner = _create_human(client, "owner@example.com")
        _grant(client, human=owner, agent=agent, role="owner")

        created = _request_approval(client, agent, key="agent-approval-1")
        replayed = _request_approval(client, agent, key="agent-approval-1")
        conflicting = _request_approval(
            client,
            agent,
            key="agent-approval-1",
            payload=_approval_payload(summary="另一项动作"),
        )
        approval_id = created.json()["approval_id"]
        csrf_token = _login(client, owner)
        listed = client.get("/api/v1/orbit/approval-requests")
        dashboard = client.get("/api/v1/orbit/dashboard")

        missing_csrf = _confirmation(client, owner, approval_id, "csrf_invalid")
        confirmation = _confirmation(client, owner, approval_id, csrf_token)
        confirmation_token = confirmation.json()["confirmation_token"]
        approved = _decide(
            client,
            approval_id,
            csrf_token,
            confirmation_token,
        )
        decision_replay = _decide(
            client,
            approval_id,
            csrf_token,
            confirmation_token,
        )
        decision_conflict = _decide(
            client,
            approval_id,
            csrf_token,
            confirmation_token,
            note="修改后的意见",
        )
        second_decision = _decide(
            client,
            approval_id,
            csrf_token,
            confirmation_token,
            key="human-decision-2",
        )
        polled = client.get(
            f"/api/v1/approval-requests/{approval_id}",
            headers=_agent_headers(agent),
        )

    assert created.status_code == 201
    assert created.json()["status"] == "pending"
    assert created.json()["execution_effect"] == "none"
    assert created.json()["security_label"] == "external_agent_content"
    assert replayed.status_code == 200
    assert replayed.headers["Idempotency-Replayed"] == "true"
    assert replayed.json()["approval_id"] == approval_id
    assert conflicting.status_code == 409
    assert missing_csrf.status_code == 403
    assert confirmation.status_code == 200
    assert confirmation.headers["Cache-Control"] == "no-store"
    assert confirmation_token.startswith("hcf_")
    assert listed.json()["items"][0]["can_decide"] is True
    assert listed.json()["items"][0]["summary"] == "发布季度银行研究报告"
    assert dashboard.json()["metrics"]["pending_approval_count"] == 1
    assert dashboard.json()["approvals"][0]["approval_id"] == approval_id
    assert dashboard.json()["capabilities"]["approvals"] is True
    assert dashboard.json()["capabilities"]["agent_actions"] is False
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["execution_effect"] == "none"
    assert decision_replay.status_code == 200
    assert decision_replay.headers["Idempotency-Replayed"] == "true"
    assert decision_conflict.status_code == 409
    assert second_decision.status_code == 409
    assert polled.status_code == 200
    assert polled.json()["status"] == "approved"
    assert polled.json()["decision_note"] == "已核对范围与接收人，可以发布。"

    with database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ApprovalRequest)) == 1
        assert session.scalar(select(func.count()).select_from(ApprovalDecision)) == 1
        assert session.scalar(select(func.count()).select_from(Message)) == 0
        success = session.scalar(
            select(HumanActionAudit).where(HumanActionAudit.action == "approval.decided")
        )
        assert success is not None
        assert success.audit_metadata["execution_effect"] == "none"


def test_approval_visibility_roles_redaction_and_non_enumeration(
    settings: Settings,
    database: Database,
) -> None:
    with _client(settings, database) as client:
        agent = _create_agent(client, "role-agent@agents.local")
        viewer = _create_human(client, "viewer@example.com")
        auditor = _create_human(client, "auditor@example.com")
        outsider = _create_human(client, "outsider@example.com")
        _grant(client, human=viewer, agent=agent, role="viewer")
        _grant(client, human=auditor, agent=agent, role="auditor")
        approval = _request_approval(client, agent, key="roles-approval")
        approval_id = approval.json()["approval_id"]

        viewer_list = client.get(
            "/api/v1/orbit/approval-requests",
            headers={"Authorization": f"Bearer {viewer['access_key']}"},
        )
        auditor_list = client.get(
            "/api/v1/orbit/approval-requests",
            headers={"Authorization": f"Bearer {auditor['access_key']}"},
        )
        outsider_get = client.get(
            f"/api/v1/orbit/approval-requests/{approval_id}",
            headers={"Authorization": f"Bearer {outsider['access_key']}"},
        )
        viewer_csrf = _login(client, viewer)
        viewer_confirmation = _confirmation(client, viewer, approval_id, viewer_csrf)

    viewer_item = viewer_list.json()["items"][0]
    assert viewer_item["summary"] == "发布季度银行研究报告"
    assert viewer_item["can_decide"] is False
    assert viewer_item["content_redacted"] is False
    auditor_item = auditor_list.json()["items"][0]
    assert auditor_item["summary"] is None
    assert auditor_item["justification"] is None
    assert auditor_item["payload"] == {}
    assert auditor_item["can_decide"] is False
    assert auditor_item["content_redacted"] is True
    assert "report-2026-q3" not in auditor_list.text
    assert outsider_get.status_code == 404
    assert viewer_confirmation.status_code == 403


def test_confirmation_is_bound_to_target_intent_human_and_current_csrf(
    settings: Settings,
    database: Database,
) -> None:
    with _client(settings, database) as client:
        agent = _create_agent(client, "binding-agent@agents.local")
        owner = _create_human(client, "binding-owner@example.com")
        other = _create_human(client, "other-owner@example.com")
        _grant(client, human=owner, agent=agent, role="owner")
        first = _request_approval(client, agent, key="binding-first")
        second = _request_approval(client, agent, key="binding-second")
        first_id = first.json()["approval_id"]
        second_id = second.json()["approval_id"]
        csrf_token = _login(client, owner)
        refreshed = client.get("/api/v1/orbit/session")
        current_csrf = refreshed.json()["csrf_token"]
        stale_csrf = _confirmation(client, owner, first_id, csrf_token)
        wrong_human = client.post(
            f"/api/v1/orbit/approval-requests/{first_id}/confirmation",
            headers={
                "Authorization": f"Bearer {other['access_key']}",
                "X-CSRF-Token": current_csrf,
            },
            json={"intent": "approve"},
        )
        confirmation = _confirmation(client, owner, first_id, current_csrf)
        raw_confirmation = confirmation.json()["confirmation_token"]
        wrong_target = _decide(
            client,
            second_id,
            current_csrf,
            raw_confirmation,
            key="wrong-target",
        )
        wrong_intent = _decide(
            client,
            first_id,
            current_csrf,
            raw_confirmation,
            key="wrong-intent",
            decision="rejected",
        )
        first_poll = client.get(
            f"/api/v1/approval-requests/{first_id}",
            headers=_agent_headers(agent),
        )
        second_poll = client.get(
            f"/api/v1/approval-requests/{second_id}",
            headers=_agent_headers(agent),
        )

    assert stale_csrf.status_code == 403
    assert wrong_human.status_code == 403
    assert wrong_human.json()["error"]["code"] == "HUMAN_REAUTHENTICATION_FAILED"
    assert wrong_target.status_code == 403
    assert wrong_intent.status_code == 403
    assert first_poll.json()["status"] == "pending"
    assert second_poll.json()["status"] == "pending"
    with database.session_factory() as session:
        denial_reasons = set(
            session.scalars(
                select(HumanActionAudit.reason_code).where(HumanActionAudit.outcome == "denied")
            ).all()
        )
    assert {
        "invalid_csrf_token",
        "human_reauthentication_mismatch",
        "human_confirmation_invalid",
    } <= denial_reasons


def test_agent_scope_cancel_and_expiration_are_terminal_without_execution(
    settings: Settings,
    database: Database,
) -> None:
    with _client(settings, database) as client:
        alice = _create_agent(client, "alice-approval@agents.local")
        bob = _create_agent(client, "bob-approval@agents.local")
        owner = _create_human(client, "cancel-owner@example.com")
        _grant(client, human=owner, agent=alice, role="owner")
        cancelled_request = _request_approval(client, alice, key="cancel-me")
        cancelled_id = cancelled_request.json()["approval_id"]
        bob_read = client.get(
            f"/api/v1/approval-requests/{cancelled_id}",
            headers=_agent_headers(bob),
        )
        cancelled = client.post(
            f"/api/v1/approval-requests/{cancelled_id}/cancel",
            headers=_agent_headers(alice),
        )
        cancel_replay = client.post(
            f"/api/v1/approval-requests/{cancelled_id}/cancel",
            headers=_agent_headers(alice),
        )

        expired_request = _request_approval(client, alice, key="expire-me")
        expired_id = expired_request.json()["approval_id"]
        with database.session_factory() as session:
            stored = session.scalar(
                select(ApprovalRequest).where(ApprovalRequest.approval_id == expired_id)
            )
            assert stored is not None
            stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            session.commit()

        expired_poll = client.get(
            f"/api/v1/approval-requests/{expired_id}",
            headers=_agent_headers(alice),
        )
        expired_list = client.get(
            "/api/v1/approval-requests",
            params={"status": "expired"},
            headers=_agent_headers(alice),
        )
        pending_list = client.get(
            "/api/v1/approval-requests",
            params={"status": "pending"},
            headers=_agent_headers(alice),
        )
        csrf_token = _login(client, owner)
        expired_confirmation = _confirmation(client, owner, expired_id, csrf_token)
        cancelled_confirmation = _confirmation(client, owner, cancelled_id, csrf_token)

    assert bob_read.status_code == 404
    assert cancelled.status_code == cancel_replay.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert expired_poll.json()["status"] == "expired"
    assert [item["approval_id"] for item in expired_list.json()["items"]] == [expired_id]
    assert pending_list.json()["items"] == []
    assert expired_confirmation.status_code == 409
    assert cancelled_confirmation.status_code == 409
    with database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ApprovalDecision)) == 0
        assert session.scalar(select(func.count()).select_from(Message)) == 0


def test_agent_cannot_spoof_requester_and_organization_owner_can_decide(
    settings: Settings,
    database: Database,
) -> None:
    with _client(settings, database) as client:
        agent = _create_agent(client, "org-approval@agents.local")
        human = _create_human(client, "org-owner@example.com")
        forged = _request_approval(
            client,
            agent,
            key="forged-requester",
            payload=_approval_payload(requested_by_agent_id=human["user"]["id"]),
        )
        with database.session_factory() as session:
            assert session.scalar(select(func.count()).select_from(ApprovalRequest)) == 0
        organization = client.post(
            "/api/v1/admin/organizations",
            headers=_admin_headers(),
            json={"slug": "approval-org", "name": "审批组织"},
        )
        assert organization.status_code == 201
        membership = client.put(
            f"/api/v1/admin/organizations/{organization.json()['id']}/members/{human['user']['id']}",
            headers=_admin_headers(),
            json={"role": "owner"},
        )
        assignment = client.put(
            f"/api/v1/admin/organizations/{organization.json()['id']}/agents/{agent['agent']['id']}",
            headers=_admin_headers(),
        )
        assert membership.status_code == assignment.status_code == 200
        approval = _request_approval(client, agent, key="org-owner-request")
        approval_id = approval.json()["approval_id"]
        csrf_token = _login(client, human)
        queue = client.get("/api/v1/orbit/approval-requests")
        confirmation = _confirmation(client, human, approval_id, csrf_token, intent="reject")
        rejected = _decide(
            client,
            approval_id,
            csrf_token,
            confirmation.json()["confirmation_token"],
            decision="rejected",
            note="范围过宽，请缩小后重新申请。",
        )

    assert forged.status_code == 422
    assert queue.json()["items"][0]["access_role"] == "operator"
    assert queue.json()["items"][0]["can_decide"] is True
    assert confirmation.status_code == 200
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"


def test_approval_schema_limits_fail_before_persistence(
    settings: Settings,
    database: Database,
) -> None:
    with _client(settings, database) as client:
        agent = _create_agent(client, "approval-schema@agents.local")
        invalid_action = _request_approval(
            client,
            agent,
            key="invalid-action",
            payload=_approval_payload(action_type="Publish Report"),
        )
        oversized = _request_approval(
            client,
            agent,
            key="oversized-payload",
            payload=_approval_payload(payload={"value": "x" * (65 * 1024)}),
        )
        too_distant = _request_approval(
            client,
            agent,
            key="distant-expiry",
            payload=_approval_payload(
                expires_at=(datetime.now(UTC) + timedelta(days=8)).isoformat()
            ),
        )

    assert invalid_action.status_code == oversized.status_code == too_distant.status_code == 422
    with database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ApprovalRequest)) == 0


@pytest.mark.concurrency
def test_concurrent_agent_retries_create_exactly_one_approval_request(
    settings: Settings,
    database: Database,
) -> None:
    with _client(settings, database) as client:
        agent = _create_agent(client, "concurrent-approval@agents.local")
        workers = 12
        start = Barrier(workers)

        def invoke(index: int):
            start.wait(timeout=10)
            return client.post(
                "/api/v1/approval-requests",
                headers={
                    **_agent_headers(agent, key="same-approval-request"),
                    "X-Request-ID": f"approval-concurrency-{index}",
                },
                json=_approval_payload(),
            )

        with ThreadPoolExecutor(max_workers=workers) as executor:
            responses = list(executor.map(invoke, range(workers)))

    assert sorted(response.status_code for response in responses) == [200] * 11 + [201]
    assert len({response.json()["approval_id"] for response in responses}) == 1
    with database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ApprovalRequest)) == 1
