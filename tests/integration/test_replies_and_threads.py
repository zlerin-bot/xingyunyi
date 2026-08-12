from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from agentpost.config import Settings
from agentpost.db import Database
from agentpost.main import create_app
from agentpost.messaging.models import AuditLog, IdempotencyRecord, Message


def register(client: TestClient, address: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/agents",
        json={
            "address": address,
            "display_name": address.partition("@")[0].title(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def bearer(registration: dict[str, Any], **extra: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {registration['api_key']}", **extra}


def send_payload(
    recipient: dict[str, Any],
    *,
    message_type: str = "message",
    subject: str = "Initial subject",
    body: str = "Initial body",
    task: dict[str, Any] | None = None,
    requires_ack: bool = True,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "to": [{"address": recipient["agent"]["address"]}],
        "type": message_type,
        "subject": subject,
        "content": {"format": "text", "body": body},
        "attachments": [],
        "priority": "normal",
        "requires_ack": requires_ack,
        "metadata": {},
        "expires_at": None,
    }
    if task is not None:
        payload["task"] = task
    return payload


def send_message(
    client: TestClient,
    sender: dict[str, Any],
    recipient: dict[str, Any],
    *,
    key: str,
    **overrides: Any,
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/messages",
        headers=bearer(sender, **{"Idempotency-Key": key}),
        json=send_payload(recipient, **overrides),
    )
    assert response.status_code == 201, response.text
    return response.json()


def reply_payload(
    *,
    message_type: str = "message",
    subject: str = "Reply subject",
    body: str = "Reply body",
    task: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    expires_at: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": message_type,
        "subject": subject,
        "content": {"format": "text", "body": body},
        "attachments": [],
        "priority": "normal",
        "requires_ack": True,
        "metadata": {},
        "expires_at": expires_at,
    }
    if task is not None:
        payload["task"] = task
    if result is not None:
        payload["result"] = result
    payload.update(extra)
    return payload


def post_reply(
    client: TestClient,
    acting_agent: dict[str, Any],
    parent_id: str,
    *,
    key: str,
    request_id: str | None = None,
    **overrides: Any,
):
    extra_headers = {"Idempotency-Key": key}
    if request_id is not None:
        extra_headers["X-Request-ID"] = request_id
    return client.post(
        f"/api/v1/messages/{parent_id}/reply",
        headers=bearer(acting_agent, **extra_headers),
        json=reply_payload(**overrides),
    )


def inbox_ids(client: TestClient, registration: dict[str, Any]) -> set[str]:
    response = client.get("/api/v1/inbox", headers=bearer(registration))
    assert response.status_code == 200, response.text
    return {str(item["message_id"]) for item in response.json()["items"]}


def message_count(database: Database) -> int:
    with database.session_factory() as session:
        return int(session.scalar(select(func.count()).select_from(Message)) or 0)


def reply_count(database: Database, parent_ids: str | list[str]) -> int:
    values = [parent_ids] if isinstance(parent_ids, str) else parent_ids
    with database.session_factory() as session:
        return int(
            session.scalar(
                select(func.count())
                .select_from(Message)
                .where(Message.reply_to_message_id.in_(values))
            )
            or 0
        )


def audit_rows(database: Database, target_id: str | None = None) -> list[AuditLog]:
    query = select(AuditLog).order_by(AuditLog.created_at, AuditLog.action)
    if target_id is not None:
        query = query.where(AuditLog.target_id == target_id)
    with database.session_factory() as session:
        return list(session.scalars(query))


def assert_protocol_error(
    response: Any,
    *,
    status_code: int,
    code: str,
    request_id: str | None = None,
) -> None:
    assert response.status_code == status_code, response.text
    payload = response.json()
    assert set(payload) == {"error"}
    error = payload["error"]
    assert error["code"] == code
    assert isinstance(error["message"], str) and error["message"]
    assert "details" in error
    assert isinstance(error["request_id"], str) and error["request_id"]
    assert response.headers["X-Request-ID"] == error["request_id"]
    if request_id is not None:
        assert error["request_id"] == request_id


def test_reply_chain_derives_identities_and_is_delivered_to_each_inbox(
    client: TestClient,
) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    original = send_message(client, alice, bob, key="chain-original")

    bob_reply_response = post_reply(
        client,
        bob,
        original["message_id"],
        key="chain-bob-reply",
        subject="Received",
        body="Received from Alice",
    )
    assert bob_reply_response.status_code == 201, bob_reply_response.text
    bob_reply = bob_reply_response.json()
    assert bob_reply["from"] == {
        "agent_id": bob["agent"]["id"],
        "address": bob["agent"]["address"],
    }
    assert bob_reply["to"] == [
        {
            "agent_id": alice["agent"]["id"],
            "address": alice["agent"]["address"],
        }
    ]
    assert bob_reply["reply_to"] == original["message_id"]
    assert bob_reply["thread_id"] == original["thread_id"]
    assert bob_reply["message_id"] in inbox_ids(client, alice)

    alice_reply_response = post_reply(
        client,
        alice,
        bob_reply["message_id"],
        key="chain-alice-reply",
        subject="Follow-up",
        body="Thank you Bob",
    )
    assert alice_reply_response.status_code == 201, alice_reply_response.text
    alice_reply = alice_reply_response.json()
    assert alice_reply["from"]["agent_id"] == alice["agent"]["id"]
    assert alice_reply["to"][0]["agent_id"] == bob["agent"]["id"]
    assert alice_reply["reply_to"] == bob_reply["message_id"]
    assert alice_reply["thread_id"] == original["thread_id"]
    assert alice_reply["message_id"] in inbox_ids(client, bob)


def test_thread_list_and_history_are_complete_visible_and_stably_ordered(
    client: TestClient,
    database: Database,
) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    original = send_message(client, alice, bob, key="thread-original")
    bob_reply_response = post_reply(
        client,
        bob,
        original["message_id"],
        key="thread-bob-reply",
    )
    assert bob_reply_response.status_code == 201, bob_reply_response.text
    bob_reply = bob_reply_response.json()
    alice_reply_response = post_reply(
        client,
        alice,
        bob_reply["message_id"],
        key="thread-alice-reply",
    )
    assert alice_reply_response.status_code == 201, alice_reply_response.text
    alice_reply = alice_reply_response.json()
    message_ids = {
        original["message_id"],
        bob_reply["message_id"],
        alice_reply["message_id"],
    }

    fixed_time = datetime(2026, 8, 12, 1, 2, 3, tzinfo=UTC)
    with database.session_factory() as session:
        session.execute(
            update(Message).where(Message.id.in_(message_ids)).values(created_at=fixed_time)
        )
        session.commit()

    expected_order = sorted(message_ids)
    for participant in (alice, bob):
        threads = client.get("/api/v1/threads", headers=bearer(participant))
        assert threads.status_code == 200, threads.text
        summary = next(
            item for item in threads.json()["items"] if item["thread_id"] == original["thread_id"]
        )
        assert summary["message_count"] == 3
        assert summary["last_message_id"] == expected_order[-1]
        assert {item["address"] for item in summary["participants"]} == {
            "alice@agents.local",
            "bob@agents.local",
        }

        history = client.get(
            f"/api/v1/threads/{original['thread_id']}",
            headers=bearer(participant),
        )
        assert history.status_code == 200, history.text
        assert history.json()["thread_id"] == original["thread_id"]
        assert [item["message_id"] for item in history.json()["messages"]] == expected_order
        assert {item["message_id"] for item in history.json()["messages"]} == message_ids


def test_unrelated_agent_cannot_read_reply_or_thread_or_create_reply(
    client: TestClient,
    database: Database,
) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    eve = register(client, "eve@agents.local")
    original = send_message(client, alice, bob, key="visibility-original")
    reply_response = post_reply(
        client,
        bob,
        original["message_id"],
        key="visibility-reply",
    )
    assert reply_response.status_code == 201, reply_response.text
    reply = reply_response.json()

    hidden_reply = client.get(
        f"/api/v1/messages/{reply['message_id']}",
        headers=bearer(eve),
    )
    assert_protocol_error(
        hidden_reply,
        status_code=404,
        code="MESSAGE_NOT_FOUND",
    )
    hidden_thread = client.get(
        f"/api/v1/threads/{original['thread_id']}",
        headers=bearer(eve),
    )
    assert_protocol_error(
        hidden_thread,
        status_code=404,
        code="THREAD_NOT_FOUND",
    )
    assert client.get("/api/v1/threads", headers=bearer(eve)).json()["items"] == []

    before = message_count(database)
    forbidden_reply = post_reply(
        client,
        eve,
        original["message_id"],
        key="eve-forbidden-reply",
        request_id="eve-reply-hidden",
    )
    assert_protocol_error(
        forbidden_reply,
        status_code=404,
        code="MESSAGE_NOT_FOUND",
        request_id="eve-reply-hidden",
    )
    assert message_count(database) == before


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("from", {"address": "eve@agents.local"}),
        ("sender", "eve@agents.local"),
        ("sender_agent_id", "00000000-0000-0000-0000-000000000000"),
        ("to", [{"address": "eve@agents.local"}]),
        ("recipient_agent_id", "00000000-0000-0000-0000-000000000000"),
        ("thread_id", "00000000-0000-0000-0000-000000000000"),
        ("reply_to", "msg_forged"),
    ],
)
def test_reply_rejects_forged_routing_and_identity_fields_without_persistence(
    client: TestClient,
    database: Database,
    field: str,
    value: Any,
) -> None:
    alice = register(client, f"alice-{field.replace('_', '-')}@agents.local")
    bob = register(client, f"bob-{field.replace('_', '-')}@agents.local")
    parent = send_message(client, alice, bob, key=f"forge-parent-{field}")
    before = message_count(database)

    response = post_reply(
        client,
        bob,
        parent["message_id"],
        key=f"forge-reply-{field}",
        **{field: value},
    )

    assert_protocol_error(
        response,
        status_code=422,
        code="SCHEMA_VALIDATION_FAILED",
    )
    assert message_count(database) == before


def test_result_and_task_reply_payload_rules_and_initial_result_rejection(
    client: TestClient,
    database: Database,
) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    task = send_message(
        client,
        alice,
        bob,
        key="payload-task-parent",
        message_type="task",
        task={"instruction": "Analyse the report", "expected_output": "markdown"},
    )
    before = message_count(database)

    missing_result = post_reply(
        client,
        bob,
        task["message_id"],
        key="missing-result",
        message_type="result",
    )
    extra_result = post_reply(
        client,
        bob,
        task["message_id"],
        key="extra-result",
        result={"status": "completed"},
    )
    missing_task = post_reply(
        client,
        bob,
        task["message_id"],
        key="missing-task",
        message_type="task",
    )
    extra_task = post_reply(
        client,
        bob,
        task["message_id"],
        key="extra-task",
        task={"instruction": "Invalid extra task"},
    )
    for response in (missing_result, extra_result, missing_task, extra_task):
        assert_protocol_error(
            response,
            status_code=422,
            code="SCHEMA_VALIDATION_FAILED",
        )
    assert message_count(database) == before

    valid_result = post_reply(
        client,
        bob,
        task["message_id"],
        key="valid-result",
        message_type="result",
        result={"status": "completed", "summary": "Analysis complete"},
    )
    assert valid_result.status_code == 201, valid_result.text
    assert valid_result.json()["result"] == {
        "status": "completed",
        "summary": "Analysis complete",
    }
    valid_task = post_reply(
        client,
        alice,
        valid_result.json()["message_id"],
        key="valid-task-reply",
        message_type="task",
        task={"instruction": "Perform a follow-up check"},
    )
    assert valid_task.status_code == 201, valid_task.text
    assert valid_task.json()["task"]["instruction"] == "Perform a follow-up check"

    initial_result = client.post(
        "/api/v1/messages",
        headers=bearer(alice, **{"Idempotency-Key": "initial-result-forbidden"}),
        json=send_payload(bob, message_type="result") | {"result": {"status": "completed"}},
    )
    assert_protocol_error(
        initial_result,
        status_code=422,
        code="SCHEMA_VALIDATION_FAILED",
    )


def test_result_reply_is_rejected_when_parent_is_not_a_task(
    client: TestClient,
    database: Database,
) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    parent = send_message(client, alice, bob, key="non-task-parent")
    before = message_count(database)

    response = post_reply(
        client,
        bob,
        parent["message_id"],
        key="orphaned-result",
        message_type="result",
        result={"status": "completed"},
    )

    assert_protocol_error(
        response,
        status_code=409,
        code="INVALID_STATE_TRANSITION",
    )
    assert message_count(database) == before


def test_reply_idempotency_binds_payload_and_parent(
    client: TestClient,
    database: Database,
) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    first_parent = send_message(client, alice, bob, key="idempotent-parent-one")
    second_parent = send_message(client, alice, bob, key="idempotent-parent-two")

    first = post_reply(
        client,
        bob,
        first_parent["message_id"],
        key="reply-idempotency-key",
        body="same body",
    )
    replay = post_reply(
        client,
        bob,
        first_parent["message_id"],
        key="reply-idempotency-key",
        body="same body",
    )
    different_payload = post_reply(
        client,
        bob,
        first_parent["message_id"],
        key="reply-idempotency-key",
        body="different body",
    )
    different_parent = post_reply(
        client,
        bob,
        second_parent["message_id"],
        key="reply-idempotency-key",
        body="same body",
    )

    assert first.status_code == 201, first.text
    assert replay.status_code == 200, replay.text
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert first.json()["message_id"] == replay.json()["message_id"]
    for response in (different_payload, different_parent):
        assert_protocol_error(
            response,
            status_code=409,
            code="IDEMPOTENCY_CONFLICT",
        )
    assert (
        reply_count(
            database,
            [first_parent["message_id"], second_parent["message_id"]],
        )
        == 1
    )


def test_idempotency_key_namespace_is_shared_by_send_and_reply(
    client: TestClient,
    database: Database,
) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    parent_one = send_message(client, alice, bob, key="namespace-parent-one")
    parent_two = send_message(client, alice, bob, key="namespace-parent-two")

    ordinary = send_message(client, bob, alice, key="namespace-send-first")
    before_first_conflict = message_count(database)
    send_then_reply = post_reply(
        client,
        bob,
        parent_one["message_id"],
        key="namespace-send-first",
    )
    assert_protocol_error(
        send_then_reply,
        status_code=409,
        code="IDEMPOTENCY_CONFLICT",
    )
    assert message_count(database) == before_first_conflict

    reply_first = post_reply(
        client,
        bob,
        parent_two["message_id"],
        key="namespace-reply-first",
    )
    assert reply_first.status_code == 201, reply_first.text
    before_second_conflict = message_count(database)
    reply_then_send = client.post(
        "/api/v1/messages",
        headers=bearer(bob, **{"Idempotency-Key": "namespace-reply-first"}),
        json=send_payload(alice, subject="Conflicting ordinary send"),
    )
    assert_protocol_error(
        reply_then_send,
        status_code=409,
        code="IDEMPOTENCY_CONFLICT",
    )
    assert message_count(database) == before_second_conflict
    assert ordinary["message_id"] != reply_first.json()["message_id"]


def test_expired_reply_is_rejected_without_persistence(
    client: TestClient,
    database: Database,
) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    parent = send_message(client, alice, bob, key="expiry-parent")
    before = message_count(database)

    response = post_reply(
        client,
        bob,
        parent["message_id"],
        key="expired-reply",
        expires_at=(datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
    )

    assert_protocol_error(
        response,
        status_code=422,
        code="SCHEMA_VALIDATION_FAILED",
    )
    assert message_count(database) == before


def test_get_thread_has_no_delivery_state_side_effects(
    client: TestClient,
    database: Database,
) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    original = send_message(client, alice, bob, key="side-effect-original")
    reply_response = post_reply(
        client,
        bob,
        original["message_id"],
        key="side-effect-reply",
    )
    assert reply_response.status_code == 201, reply_response.text
    reply = reply_response.json()

    for participant in (alice, bob):
        history = client.get(
            f"/api/v1/threads/{original['thread_id']}",
            headers=bearer(participant),
        )
        assert history.status_code == 200, history.text
        assert client.get("/api/v1/threads", headers=bearer(participant)).status_code == 200

    with database.session_factory() as session:
        messages = list(
            session.scalars(
                select(Message)
                .where(Message.id.in_([original["message_id"], reply["message_id"]]))
                .order_by(Message.id)
            )
        )
        assert len(messages) == 2
        assert all(message.delivery.delivery_status == "delivered" for message in messages)
        assert all(message.delivery.read_at is None for message in messages)
        assert all(message.delivery.acked_at is None for message in messages)
    assert reply["message_id"] in inbox_ids(client, alice)
    assert original["message_id"] in inbox_ids(client, bob)


def test_thread_persists_across_application_recreation(
    settings: Settings,
    database: Database,
) -> None:
    with TestClient(create_app(settings=settings, database=database)) as first_client:
        alice = register(first_client, "alice@agents.local")
        bob = register(first_client, "bob@agents.local")
        original = send_message(first_client, alice, bob, key="restart-original")
        reply_response = post_reply(
            first_client,
            bob,
            original["message_id"],
            key="restart-reply",
        )
        assert reply_response.status_code == 201, reply_response.text
        expected_ids = [original["message_id"], reply_response.json()["message_id"]]

    restarted_database = Database(settings.database_url)
    with TestClient(create_app(settings=settings, database=restarted_database)) as restarted_client:
        history = restarted_client.get(
            f"/api/v1/threads/{original['thread_id']}",
            headers=bearer(alice),
        )
        assert history.status_code == 200, history.text
        assert [item["message_id"] for item in history.json()["messages"]] == expected_ids
        assert any(
            item["thread_id"] == original["thread_id"]
            for item in restarted_client.get("/api/v1/threads", headers=bearer(bob)).json()["items"]
        )


def test_reply_audit_excludes_subject_body_idempotency_key_and_api_keys(
    client: TestClient,
    database: Database,
) -> None:
    subject = "REPLY_SUBJECT_CANARY_1d35b9"
    body = "REPLY_BODY_CANARY_507ac2"
    key = "REPLY_IDEMPOTENCY_CANARY_3ae818"
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    parent = send_message(client, alice, bob, key="audit-parent")
    reply_response = post_reply(
        client,
        bob,
        parent["message_id"],
        key=key,
        subject=subject,
        body=body,
    )
    assert reply_response.status_code == 201, reply_response.text
    reply_id = reply_response.json()["message_id"]

    rows = audit_rows(database, reply_id)
    assert [row.action for row in rows] == ["message.replied"]
    serialized = json.dumps(
        [
            {
                "actor_agent_id": str(row.actor_agent_id),
                "action": row.action,
                "target_type": row.target_type,
                "target_id": row.target_id,
                "outcome": row.outcome,
                "reason_code": row.reason_code,
                "request_id": row.request_id,
                "metadata": row.audit_metadata,
            }
            for row in rows
        ],
        sort_keys=True,
    )
    for secret in (subject, body, key, alice["api_key"], bob["api_key"]):
        assert secret not in serialized


def test_concurrent_same_key_reply_creates_exactly_one_message_and_record(
    client: TestClient,
    database: Database,
) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    parent = send_message(client, alice, bob, key="concurrent-parent")
    parent_id = parent["message_id"]
    workers = 8
    start = Barrier(workers)

    def invoke(index: int):
        start.wait(timeout=5)
        return post_reply(
            client,
            bob,
            parent_id,
            key="concurrent-reply-key",
            request_id=f"concurrent-reply-{index}",
            subject="One durable reply",
            body="The same reply payload",
        )

    with ThreadPoolExecutor(max_workers=workers) as executor:
        responses = list(executor.map(invoke, range(workers)))

    assert sorted(response.status_code for response in responses) == [200] * 7 + [201]
    reply_ids = {response.json()["message_id"] for response in responses}
    assert len(reply_ids) == 1
    assert reply_count(database, parent_id) == 1
    with database.session_factory() as session:
        records = list(
            session.scalars(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.sender_agent_id == UUID(bob["agent"]["id"]),
                    IdempotencyRecord.idempotency_key == "concurrent-reply-key",
                )
            )
        )
    assert len(records) == 1
    assert records[0].operation == "reply_message"
    assert (
        sum(
            row.action == "message.replied" and row.target_id in reply_ids
            for row in audit_rows(database)
        )
        == 1
    )
