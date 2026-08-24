from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from agentpost.config import Settings
from agentpost.control.models import (
    AgentOwnership,
    HumanActionConfirmation,
)
from agentpost.db import Database
from agentpost.identity.models import Agent, AgentApiKey
from agentpost.main import create_app
from agentpost.messaging.models import Delivery, Message
from agentpost.onboarding.models import (
    AgentConnectorBinding,
    AgentPairingSession,
    ConnectorInstance,
)

ADMIN_KEY = "admin-secret-admin-secret-admin-secret"


def _runtime_settings(settings: Settings, **updates: Any) -> Settings:
    values: dict[str, Any] = {
        "environment": "test",
        "database_url": settings.database_url,
        "storage_path": settings.storage_path,
        "api_key_pepper": "onboarding-agent-pepper",
        "human_api_key_pepper": "onboarding-human-pepper",
        "cursor_secret": "onboarding-cursor-secret",
        "pairing_secret": "onboarding-pairing-secret",
        "registration_token": "registration-secret",
        "admin_token": ADMIN_KEY,
        "pairing_enabled": True,
        "managed_agent_domain": "agents.local",
        "public_base_url": "https://agentpost.example",
        "pairing_ttl_seconds": 600,
        "pairing_poll_interval_seconds": 5,
        "log_level": "WARNING",
    }
    values.update(updates)
    return Settings(**values)


def _create_human(client: TestClient, email: str = "owner@example.com") -> dict[str, Any]:
    response = client.post(
        "/api/v1/admin/humans",
        headers={"Authorization": f"Bearer {ADMIN_KEY}"},
        json={"email": email, "display_name": "北辰"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _login(client: TestClient, human: dict[str, Any]) -> str:
    response = client.post(
        "/api/v1/orbit/session",
        headers={"Authorization": f"Bearer {human['access_key']}"},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["csrf_token"])


def _start_pairing(
    client: TestClient,
    *,
    connector_type: str = "codex",
    name: str = "Codex on Mars MacBook",
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/connect/pairings",
        json={
            "connector_type": connector_type,
            "display_name": name,
            "device_name": "Mars MacBook",
            "client_version": "1.0.0",
            "capabilities": ["financial-research", "document-analysis"],
        },
    )
    assert response.status_code == 201, response.text
    assert response.headers["Cache-Control"] == "no-store"
    return response.json()


def _confirmation(
    client: TestClient,
    *,
    human: dict[str, Any],
    csrf: str,
    pairing: dict[str, Any],
    intent: str = "approve",
    user_code: str | None = None,
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/orbit/pairings/{pairing['pairing_id']}/confirmation",
        headers={
            "Authorization": f"Bearer {human['access_key']}",
            "X-CSRF-Token": csrf,
        },
        json={"intent": intent, "user_code": user_code or pairing["user_code"]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _decide(
    client: TestClient,
    *,
    pairing: dict[str, Any],
    csrf: str,
    confirmation: dict[str, Any],
    payload: dict[str, Any],
    idempotency_key: str,
):
    return client.post(
        f"/api/v1/orbit/pairings/{pairing['pairing_id']}/decision",
        headers={
            "X-CSRF-Token": csrf,
            "X-Human-Confirmation": confirmation["confirmation_token"],
            "Idempotency-Key": idempotency_key,
        },
        json=payload,
    )


def _register_agent(client: TestClient, address: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/agents",
        headers={"X-Registration-Token": "registration-secret"},
        json={"address": address, "display_name": "Alice"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_zero_config_pairing_creates_owned_agent_and_preserves_offline_inbox(
    settings: Settings,
    database: Database,
) -> None:
    runtime = _runtime_settings(settings)
    with TestClient(create_app(settings=runtime, database=database)) as client:
        pairing = _start_pairing(client)
        assert pairing["device_code"].startswith("dvc_")
        assert pairing["user_code"] in pairing["verification_uri_complete"]
        assert pairing["pairing_id"] in pairing["verification_uri_complete"]

        pending = client.post(
            "/api/v1/connect/pairings/token",
            json={"device_code": pairing["device_code"]},
        )
        too_fast = client.post(
            "/api/v1/connect/pairings/token",
            json={"device_code": pairing["device_code"]},
        )
        assert pending.status_code == 202
        assert pending.json() == {
            "status": "pending",
            "interval": 5,
            "agent": None,
            "connector": None,
            "api_key": None,
        }
        assert too_fast.status_code == 429
        assert too_fast.headers["Retry-After"]

        human = _create_human(client)
        csrf = _login(client, human)
        preview = client.get(f"/api/v1/orbit/pairings/{pairing['pairing_id']}")
        assert preview.status_code == 200
        assert preview.json()["security_label"] == "external_agent_content"
        assert preview.json()["connector_type"] == "codex"
        assert pairing["user_code"] not in preview.text

        wrong_code = client.post(
            f"/api/v1/orbit/pairings/{pairing['pairing_id']}/confirmation",
            headers={
                "Authorization": f"Bearer {human['access_key']}",
                "X-CSRF-Token": csrf,
            },
            json={"intent": "approve", "user_code": "0000-0000"},
        )
        assert wrong_code.status_code == 403
        assert wrong_code.json()["error"]["code"] == "PAIRING_CODE_INVALID"

        confirmation = _confirmation(
            client,
            human=human,
            csrf=csrf,
            pairing=pairing,
        )
        decision_payload = {
            "decision": "approved",
            "local_agent_id": "pluto",
            "display_name": "冥王星研究员",
            "description": "由 Human 明确授权的研究 Agent",
            "capabilities": ["financial-research"],
        }
        approved = _decide(
            client,
            pairing=pairing,
            csrf=csrf,
            confirmation=confirmation,
            payload=decision_payload,
            idempotency_key="pairing-approve-1",
        )
        replay = _decide(
            client,
            pairing=pairing,
            csrf=csrf,
            confirmation=confirmation,
            payload=decision_payload,
            idempotency_key="pairing-approve-1",
        )
        assert approved.status_code == replay.status_code == 200
        assert approved.json()["pairing"]["agent"]["address"] == "pluto@agents.local"
        assert approved.json()["connector"]["status"] == "active"
        assert replay.headers["Idempotency-Replayed"] == "true"

        issued = client.post(
            "/api/v1/connect/pairings/token",
            json={"device_code": pairing["device_code"]},
        )
        issued_again = client.post(
            "/api/v1/connect/pairings/token",
            json={"device_code": pairing["device_code"]},
        )
        assert issued.status_code == issued_again.status_code == 200
        agent_key = str(issued.json()["api_key"])
        assert agent_key.startswith("agt_")
        assert issued_again.json()["api_key"] == agent_key
        assert issued.json()["agent"]["address"] == "pluto@agents.local"

        empty_inbox = client.get(
            "/api/v1/inbox?status=unread",
            headers={"Authorization": f"Bearer {agent_key}"},
        )
        assert empty_inbox.status_code == 200
        assert empty_inbox.json()["items"] == []

        alice = _register_agent(client, "alice@agents.local")
        accepted = client.post(
            "/api/v1/messages",
            headers={
                "Authorization": f"Bearer {alice['api_key']}",
                "Idempotency-Key": "alice-to-offline-pluto",
            },
            json={
                "to": [{"address": "pluto@agents.local"}],
                "type": "message",
                "subject": "离线投递",
                "content": {"format": "text", "body": "Pluto 下线时也应持久化"},
            },
        )
        assert accepted.status_code == 201

    with TestClient(create_app(settings=runtime, database=database)) as restarted:
        inbox = restarted.get(
            "/api/v1/inbox?status=unread",
            headers={"Authorization": f"Bearer {agent_key}"},
        )
        connectors = restarted.get(
            "/api/v1/orbit/connectors",
            headers={"Authorization": f"Bearer {human['access_key']}"},
        )
        assert inbox.status_code == 200
        assert [item["subject"] for item in inbox.json()["items"]] == ["离线投递"]
        assert connectors.status_code == 200
        assert connectors.json()["items"][0]["is_current"] is True
        assert connectors.json()["items"][0]["last_seen_at"] is not None

    with database.session_factory() as session:
        stored_pairing = session.scalar(select(AgentPairingSession))
        credential = session.scalar(
            select(AgentApiKey).where(AgentApiKey.connector_instance_id.is_not(None))
        )
        assert stored_pairing is not None and credential is not None
        assert stored_pairing.status == "consumed"
        assert stored_pairing.device_code_digest != pairing["device_code"]
        assert stored_pairing.user_code_digest != pairing["user_code"]
        assert credential.key_digest != agent_key
        assert agent_key not in credential.key_digest
        assert session.scalar(select(func.count()).select_from(AgentOwnership)) == 1
        assert session.scalar(select(func.count()).select_from(ConnectorInstance)) == 1
        assert session.scalar(select(func.count()).select_from(AgentConnectorBinding)) == 1
        assert session.scalar(select(func.count()).select_from(Message)) == 1
        assert session.scalar(select(func.count()).select_from(Delivery)) == 1


def test_owner_can_revoke_connector_without_deleting_agent_or_inbox(
    settings: Settings,
    database: Database,
) -> None:
    runtime = _runtime_settings(settings)
    with TestClient(create_app(settings=runtime, database=database)) as client:
        pairing = _start_pairing(client, connector_type="workbuddy")
        human = _create_human(client, "revoke@example.com")
        csrf = _login(client, human)
        confirmation = _confirmation(client, human=human, csrf=csrf, pairing=pairing)
        approved = _decide(
            client,
            pairing=pairing,
            csrf=csrf,
            confirmation=confirmation,
            payload={"decision": "approved", "local_agent_id": "daily-report"},
            idempotency_key="approve-revoke-agent",
        )
        connector_id = approved.json()["connector"]["connector_id"]
        token = client.post(
            "/api/v1/connect/pairings/token",
            json={"device_code": pairing["device_code"]},
        ).json()["api_key"]
        assert (
            client.get(
                "/api/v1/inbox",
                headers={"Authorization": f"Bearer {token}"},
            ).status_code
            == 200
        )

        revoke_confirmation = client.post(
            f"/api/v1/orbit/connectors/{connector_id}/confirmation",
            headers={
                "Authorization": f"Bearer {human['access_key']}",
                "X-CSRF-Token": csrf,
            },
        )
        assert revoke_confirmation.status_code == 200
        revoked = client.delete(
            f"/api/v1/orbit/connectors/{connector_id}",
            headers={
                "X-CSRF-Token": csrf,
                "X-Human-Confirmation": revoke_confirmation.json()["confirmation_token"],
            },
        )
        replay = client.delete(
            f"/api/v1/orbit/connectors/{connector_id}",
            headers={
                "X-CSRF-Token": csrf,
                "X-Human-Confirmation": revoke_confirmation.json()["confirmation_token"],
            },
        )
        rejected_key = client.get(
            "/api/v1/inbox",
            headers={"Authorization": f"Bearer {token}"},
        )
        connectors = client.get("/api/v1/orbit/connectors").json()["items"]

    assert revoked.status_code == replay.status_code == 204
    assert rejected_key.status_code == 401
    assert connectors[0]["status"] == "revoked"
    assert connectors[0]["is_current"] is False
    with database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Agent)) == 1
        assert session.scalar(select(func.count()).select_from(AgentOwnership)) == 1
        assert session.scalar(select(func.count()).select_from(AgentConnectorBinding)) == 0
        credential = session.scalar(select(AgentApiKey))
        assert credential is not None and credential.revoked_at is not None


def test_denied_expired_and_unknown_pairings_never_create_identity(
    settings: Settings,
    database: Database,
) -> None:
    runtime = _runtime_settings(settings)
    with TestClient(create_app(settings=runtime, database=database)) as client:
        denied_pairing = _start_pairing(client, connector_type="manus")
        human = _create_human(client, "deny@example.com")
        csrf = _login(client, human)
        confirmation = _confirmation(
            client,
            human=human,
            csrf=csrf,
            pairing=denied_pairing,
            intent="deny",
        )
        denied = _decide(
            client,
            pairing=denied_pairing,
            csrf=csrf,
            confirmation=confirmation,
            payload={"decision": "denied"},
            idempotency_key="deny-manus-pairing",
        )
        denied_poll = client.post(
            "/api/v1/connect/pairings/token",
            json={"device_code": denied_pairing["device_code"]},
        )
        unknown = client.post(
            "/api/v1/connect/pairings/token",
            json={"device_code": "dvc_" + "x" * 43},
        )

        expired_pairing = _start_pairing(client, connector_type="claude")
        with database.session_factory() as session:
            stored = session.scalar(
                select(AgentPairingSession).where(
                    AgentPairingSession.pairing_id == expired_pairing["pairing_id"]
                )
            )
            assert stored is not None
            stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            session.commit()
        expired = client.post(
            "/api/v1/connect/pairings/token",
            json={"device_code": expired_pairing["device_code"]},
        )

    assert denied.status_code == 200
    assert denied.json()["pairing"]["status"] == "denied"
    assert denied_poll.status_code == 403
    assert unknown.status_code == 404
    assert expired.status_code == 410
    with database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Agent)) == 0
        assert session.scalar(select(func.count()).select_from(ConnectorInstance)) == 0
        assert session.scalar(select(func.count()).select_from(AgentApiKey)) == 0


def test_pairing_is_human_isolated_and_address_conflict_rolls_back(
    settings: Settings,
    database: Database,
) -> None:
    runtime = _runtime_settings(settings)
    with TestClient(create_app(settings=runtime, database=database)) as client:
        _register_agent(client, "taken@agents.local")
        pairing = _start_pairing(client)
        owner = _create_human(client, "first@example.com")
        csrf = _login(client, owner)
        confirmation = _confirmation(client, human=owner, csrf=csrf, pairing=pairing)
        conflict = _decide(
            client,
            pairing=pairing,
            csrf=csrf,
            confirmation=confirmation,
            payload={"decision": "approved", "local_agent_id": "taken"},
            idempotency_key="conflicting-address",
        )
        assert conflict.status_code == 409

        confirmation = _confirmation(client, human=owner, csrf=csrf, pairing=pairing)
        approved = _decide(
            client,
            pairing=pairing,
            csrf=csrf,
            confirmation=confirmation,
            payload={"decision": "approved", "local_agent_id": "available"},
            idempotency_key="available-address",
        )
        assert approved.status_code == 200

        client.delete(
            "/api/v1/orbit/session",
            headers={"X-CSRF-Token": csrf},
        )
        outsider = _create_human(client, "second@example.com")
        _login(client, outsider)
        hidden_pairing = client.get(f"/api/v1/orbit/pairings/{pairing['pairing_id']}")
        visible_connectors = client.get("/api/v1/orbit/connectors")

    assert hidden_pairing.status_code == 404
    assert visible_connectors.status_code == 200
    assert visible_connectors.json()["items"] == []
    with database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Agent)) == 2
        assert session.scalar(select(func.count()).select_from(ConnectorInstance)) == 1
        assert session.scalar(select(func.count()).select_from(HumanActionConfirmation)) == 2


def test_pairing_can_be_disabled_without_exposing_public_surface(
    settings: Settings,
    database: Database,
) -> None:
    runtime = _runtime_settings(settings, pairing_enabled=False)
    with TestClient(create_app(settings=runtime, database=database)) as client:
        create = client.post(
            "/api/v1/connect/pairings",
            json={"connector_type": "codex", "display_name": "Codex"},
        )
        poll = client.post(
            "/api/v1/connect/pairings/token",
            json={"device_code": "dvc_" + "x" * 43},
        )

    assert create.status_code == poll.status_code == 404
    assert create.json()["error"]["code"] == "PAIRING_NOT_AVAILABLE"
    with database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(AgentPairingSession)) == 0


def test_connector_api_key_is_bound_to_connector_record(
    settings: Settings,
    database: Database,
) -> None:
    runtime = _runtime_settings(settings)
    with TestClient(create_app(settings=runtime, database=database)) as client:
        pairing = _start_pairing(client, connector_type="minimax-code")
        human = _create_human(client, "binding@example.com")
        csrf = _login(client, human)
        confirmation = _confirmation(client, human=human, csrf=csrf, pairing=pairing)
        _decide(
            client,
            pairing=pairing,
            csrf=csrf,
            confirmation=confirmation,
            payload={"decision": "approved", "local_agent_id": "minimax-worker"},
            idempotency_key="minimax-binding",
        )
        issued = client.post(
            "/api/v1/connect/pairings/token",
            json={"device_code": pairing["device_code"]},
        )
        assert issued.status_code == 200

    connector_id = issued.json()["connector"]["connector_id"]
    with database.session_factory() as session:
        connector = session.scalar(
            select(ConnectorInstance).where(ConnectorInstance.connector_id == connector_id)
        )
        credential = session.scalar(select(AgentApiKey))
        binding = session.scalar(select(AgentConnectorBinding))
        ownership = session.scalar(select(AgentOwnership))
        assert connector is not None
        assert credential is not None and credential.connector_instance_id == connector.id
        assert binding is not None and binding.connector_instance_id == connector.id
        assert ownership is not None and ownership.human_user_id == UUID(human["user"]["id"])


def test_existing_agent_moves_to_new_connector_and_rotates_credential(
    settings: Settings,
    database: Database,
) -> None:
    runtime = _runtime_settings(settings)
    with TestClient(create_app(settings=runtime, database=database)) as client:
        human = _create_human(client, "migration-owner@example.com")
        csrf = _login(client, human)

        first_pairing = _start_pairing(client, connector_type="codex", name="Codex 旧宿主")
        first_confirmation = _confirmation(
            client,
            human=human,
            csrf=csrf,
            pairing=first_pairing,
        )
        first_approved = _decide(
            client,
            pairing=first_pairing,
            csrf=csrf,
            confirmation=first_confirmation,
            payload={"decision": "approved", "local_agent_id": "stable-researcher"},
            idempotency_key="approve-first-connector",
        )
        assert first_approved.status_code == 200, first_approved.text
        agent_id = first_approved.json()["pairing"]["agent"]["id"]
        agent_address = first_approved.json()["pairing"]["agent"]["address"]
        old_connector_id = first_approved.json()["connector"]["connector_id"]
        old_key = client.post(
            "/api/v1/connect/pairings/token",
            json={"device_code": first_pairing["device_code"]},
        ).json()["api_key"]

        replacement = _start_pairing(
            client,
            connector_type="openclaw",
            name="OpenClaw 新宿主",
        )
        replacement_confirmation = _confirmation(
            client,
            human=human,
            csrf=csrf,
            pairing=replacement,
        )
        migrated = _decide(
            client,
            pairing=replacement,
            csrf=csrf,
            confirmation=replacement_confirmation,
            payload={"decision": "approved", "existing_agent_id": agent_id},
            idempotency_key="replace-codex-with-openclaw",
        )
        assert migrated.status_code == 200, migrated.text
        assert migrated.json()["pairing"]["agent"] == {
            "id": agent_id,
            "address": agent_address,
            "display_name": "stable-researcher",
        }
        assert migrated.json()["connector"]["connector_id"] != old_connector_id
        assert (
            client.get(
                "/api/v1/inbox",
                headers={"Authorization": f"Bearer {old_key}"},
            ).status_code
            == 401
        )

        replacement_token = client.post(
            "/api/v1/connect/pairings/token",
            json={"device_code": replacement["device_code"]},
        )
        assert replacement_token.status_code == 200, replacement_token.text
        replacement_key = replacement_token.json()["api_key"]
        heartbeat = client.post(
            "/api/v1/connect/heartbeat",
            headers={"Authorization": f"Bearer {replacement_key}"},
            json={"health_status": "degraded", "last_error_code": "POLL_TIMEOUT"},
        )
        assert heartbeat.status_code == 200, heartbeat.text
        assert heartbeat.json()["current"] is True
        assert heartbeat.json()["connector"]["health_status"] == "degraded"
        assert heartbeat.json()["recommended_interval_seconds"] == 30

        rotated = client.post(
            "/api/v1/connect/credentials/rotate",
            headers={"Authorization": f"Bearer {replacement_key}"},
        )
        assert rotated.status_code == 200, rotated.text
        rotated_key = rotated.json()["api_key"]
        assert rotated_key.startswith("agt_")
        assert rotated_key != replacement_key
        assert (
            client.get(
                "/api/v1/inbox",
                headers={"Authorization": f"Bearer {replacement_key}"},
            ).status_code
            == 401
        )
        assert (
            client.get(
                "/api/v1/inbox",
                headers={"Authorization": f"Bearer {rotated_key}"},
            ).status_code
            == 200
        )
        connectors = client.get("/api/v1/orbit/connectors").json()["items"]
        assert [item["status"] for item in connectors] == ["active", "replaced"]
        assert [item["is_current"] for item in connectors] == [True, False]

    with database.session_factory() as session:
        connectors = session.scalars(
            select(ConnectorInstance).order_by(ConnectorInstance.created_at)
        ).all()
        assert session.scalar(select(func.count()).select_from(Agent)) == 1
        assert session.scalar(select(func.count()).select_from(AgentOwnership)) == 1
        assert session.scalar(select(func.count()).select_from(AgentConnectorBinding)) == 1
        assert len(connectors) == 2
        assert connectors[0].status == "replaced"
        assert connectors[0].revocation_reason == "replaced_by_new_connector"
        assert connectors[1].health_status == "degraded"
        assert connectors[1].last_heartbeat_at is not None
        assert connectors[1].credential_rotated_at is not None
        current_credentials = session.scalars(
            select(AgentApiKey).where(AgentApiKey.revoked_at.is_(None))
        ).all()
        assert len(current_credentials) == 1
        assert current_credentials[0].key_digest != rotated_key


def test_existing_agent_pairing_is_owner_only_and_profile_fields_are_immutable(
    settings: Settings,
    database: Database,
) -> None:
    runtime = _runtime_settings(settings)
    with TestClient(create_app(settings=runtime, database=database)) as client:
        owner = _create_human(client, "existing-owner@example.com")
        owner_csrf = _login(client, owner)
        original = _start_pairing(client)
        original_confirmation = _confirmation(
            client,
            human=owner,
            csrf=owner_csrf,
            pairing=original,
        )
        approved = _decide(
            client,
            pairing=original,
            csrf=owner_csrf,
            confirmation=original_confirmation,
            payload={"decision": "approved", "local_agent_id": "private-agent"},
            idempotency_key="create-private-agent",
        )
        agent_id = approved.json()["pairing"]["agent"]["id"]
        client.delete("/api/v1/orbit/session", headers={"X-CSRF-Token": owner_csrf})

        outsider = _create_human(client, "existing-outsider@example.com")
        outsider_csrf = _login(client, outsider)
        attempt = _start_pairing(client, connector_type="manus")
        attempt_confirmation = _confirmation(
            client,
            human=outsider,
            csrf=outsider_csrf,
            pairing=attempt,
        )
        hidden = _decide(
            client,
            pairing=attempt,
            csrf=outsider_csrf,
            confirmation=attempt_confirmation,
            payload={"decision": "approved", "existing_agent_id": agent_id},
            idempotency_key="outsider-cannot-bind",
        )
        assert hidden.status_code == 404
        assert hidden.json()["error"]["code"] == "AGENT_NOT_OWNED"

        invalid = _decide(
            client,
            pairing=attempt,
            csrf=outsider_csrf,
            confirmation=attempt_confirmation,
            payload={
                "decision": "approved",
                "existing_agent_id": agent_id,
                "display_name": "伪造改名",
            },
            idempotency_key="existing-profile-is-immutable",
        )
        assert invalid.status_code == 422

        registered = _register_agent(client, "legacy@agents.local")
        non_connector_rotation = client.post(
            "/api/v1/connect/credentials/rotate",
            headers={"Authorization": f"Bearer {registered['api_key']}"},
        )
        assert non_connector_rotation.status_code == 409

    with database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Agent)) == 2
        assert session.scalar(select(func.count()).select_from(ConnectorInstance)) == 1


def test_pairing_creation_has_durable_ip_rate_limit(
    settings: Settings,
    database: Database,
) -> None:
    runtime = _runtime_settings(
        settings,
        pairing_create_ip_limit=2,
        pairing_rate_window_seconds=3600,
    )
    with TestClient(create_app(settings=runtime, database=database)) as client:
        for index in range(2):
            created = client.post(
                "/api/v1/connect/pairings",
                json={
                    "connector_type": "codex",
                    "display_name": f"Pilot Connector {index}",
                    "capabilities": [],
                },
            )
            assert created.status_code == 201, created.text
        limited = client.post(
            "/api/v1/connect/pairings",
            json={
                "connector_type": "codex",
                "display_name": "Third Connector",
                "capabilities": [],
            },
        )

    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"
    assert int(limited.headers["Retry-After"]) >= 1
    with database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(AgentPairingSession)) == 2
