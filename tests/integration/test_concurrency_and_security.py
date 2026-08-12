from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from agentpost.attachments.models import Attachment
from agentpost.db import Database
from agentpost.identity.models import Agent, AgentApiKey
from agentpost.messaging.models import AuditLog, Delivery, IdempotencyRecord, Message


def register(client: TestClient, address: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/agents",
        json={"address": address, "display_name": address.partition("@")[0].title()},
    )
    assert response.status_code == 201, response.text
    return response.json()


def bearer(registration: dict[str, Any], **extra: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {registration['api_key']}", **extra}


def payload(
    recipient: dict[str, Any],
    *,
    subject: str = "Concurrent message",
    body: str = "Untrusted concurrent body",
    **extra: Any,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "to": [{"address": recipient["agent"]["address"]}],
        "type": "message",
        "subject": subject,
        "content": {"format": "text", "body": body},
        "attachments": [],
        "priority": "normal",
        "requires_ack": True,
        "metadata": {},
        "expires_at": None,
    }
    result.update(extra)
    return result


def send(
    client: TestClient,
    sender: dict[str, Any],
    recipient: dict[str, Any],
    *,
    key: str,
    subject: str = "Concurrent message",
    body: str = "Untrusted concurrent body",
):
    return client.post(
        "/api/v1/messages",
        headers=bearer(sender, **{"Idempotency-Key": key}),
        json=payload(recipient, subject=subject, body=body),
    )


def table_counts(database: Database) -> dict[str, int]:
    models = (Agent, AgentApiKey, Message, Delivery, IdempotencyRecord, Attachment)
    with database.session_factory() as session:
        return {
            model.__tablename__: int(session.scalar(select(func.count()).select_from(model)) or 0)
            for model in models
        }


@pytest.mark.concurrency
def test_one_hundred_agents_send_concurrently_without_loss_or_duplication(
    client: TestClient,
    database: Database,
) -> None:
    # Registration setup is deliberately sequential: this case isolates concurrent delivery.
    senders = [register(client, f"sender-{index:03d}@agents.local") for index in range(100)]
    receiver = register(client, "sink@agents.local")
    workers = 20
    start = Barrier(workers)

    def invoke(index: int):
        # Release in five waves of twenty without serializing the actual request work.
        start.wait(timeout=10)
        return send(
            client,
            senders[index],
            receiver,
            key=f"hundred-agent-{index:03d}",
            body=f"message-{index:03d}",
        )

    responses = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for offset in range(0, 100, workers):
            responses.extend(executor.map(invoke, range(offset, offset + workers)))

    assert [response.status_code for response in responses] == [201] * 100
    message_ids = {response.json()["message_id"] for response in responses}
    assert len(message_ids) == 100
    counts = table_counts(database)
    assert counts["messages"] == 100
    assert counts["deliveries"] == 100
    assert counts["idempotency_records"] == 100

    all_inbox_ids: list[str] = []
    cursor = None
    while True:
        params: dict[str, Any] = {"limit": 23}
        if cursor is not None:
            params["cursor"] = cursor
        page = client.get("/api/v1/inbox", params=params, headers=bearer(receiver))
        assert page.status_code == 200, page.text
        all_inbox_ids.extend(item["message_id"] for item in page.json()["items"])
        cursor = page.json().get("next_cursor")
        if cursor is None:
            break
    assert len(all_inbox_ids) == len(set(all_inbox_ids)) == 100
    assert set(all_inbox_ids) == message_ids


@pytest.mark.concurrency
def test_thirty_two_same_sender_same_key_requests_create_exactly_one_delivery(
    client: TestClient,
    database: Database,
) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    workers = 32
    start = Barrier(workers)

    def invoke(index: int):
        start.wait(timeout=10)
        return client.post(
            "/api/v1/messages",
            headers=bearer(
                alice,
                **{
                    "Idempotency-Key": "same-key-thirty-two",
                    "X-Request-ID": f"same-key-{index}",
                },
            ),
            json=payload(bob, body="Exactly one durable message"),
        )

    with ThreadPoolExecutor(max_workers=workers) as executor:
        responses = list(executor.map(invoke, range(workers)))

    assert sorted(response.status_code for response in responses) == [200] * 31 + [201]
    message_ids = {response.json()["message_id"] for response in responses}
    assert len(message_ids) == 1
    counts = table_counts(database)
    assert counts["messages"] == 1
    assert counts["deliveries"] == 1
    assert counts["idempotency_records"] == 1
    with database.session_factory() as session:
        accepted_audits = list(
            session.scalars(
                select(AuditLog).where(
                    AuditLog.action == "message.accepted",
                    AuditLog.target_id.in_(message_ids),
                )
            )
        )
    assert len(accepted_audits) == 1


@pytest.mark.concurrency
def test_concurrent_read_and_ack_never_regress_acked_state(
    client: TestClient,
    database: Database,
) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    accepted = send(client, alice, bob, key="mixed-transition")
    assert accepted.status_code == 201, accepted.text
    message_id = accepted.json()["message_id"]
    workers = 32
    start = Barrier(workers)

    def invoke(index: int):
        start.wait(timeout=10)
        action = "read" if index % 2 == 0 else "ack"
        return client.post(
            f"/api/v1/messages/{message_id}/{action}",
            headers=bearer(bob, **{"X-Request-ID": f"mixed-transition-{index}"}),
        )

    with ThreadPoolExecutor(max_workers=workers) as executor:
        responses = list(executor.map(invoke, range(workers)))

    assert [response.status_code for response in responses] == [200] * workers
    assert all(response.json()["delivery"]["status"] in {"read", "acked"} for response in responses)
    final = client.get(f"/api/v1/messages/{message_id}", headers=bearer(alice))
    assert final.status_code == 200, final.text
    assert final.json()["delivery"]["status"] == "acked"
    assert final.json()["delivery"]["read_at"] is not None
    assert final.json()["delivery"]["acked_at"] is not None
    with database.session_factory() as session:
        stored = session.scalar(select(Delivery).where(Delivery.message_id == message_id))
        assert stored is not None
        assert stored.delivery_status == "acked"
        assert stored.read_at is not None and stored.acked_at is not None
        audits = list(
            session.scalars(
                select(AuditLog).where(
                    AuditLog.target_id == message_id,
                    AuditLog.action.in_(["message.read", "message.ack"]),
                )
            )
        )
    assert sum(row.action == "message.ack" for row in audits) == 1
    assert sum(row.action == "message.read" for row in audits) <= 1


@pytest.mark.parametrize(
    ("forged_field", "forged_value"),
    [
        ("from", {"address": "eve@agents.local"}),
        ("sender", "eve@agents.local"),
        ("sender_agent_id", "00000000-0000-0000-0000-000000000000"),
        ("status", "acked"),
        ("delivered_at", "2026-08-12T00:00:00Z"),
    ],
)
def test_spoofed_identity_and_server_owned_state_are_rejected_before_persistence(
    client: TestClient,
    database: Database,
    forged_field: str,
    forged_value: Any,
) -> None:
    alice = register(client, f"alice-{forged_field.replace('_', '-')}@agents.local")
    bob = register(client, f"bob-{forged_field.replace('_', '-')}@agents.local")
    before = table_counts(database)
    forged = payload(bob, **{forged_field: forged_value})

    response = client.post(
        "/api/v1/messages",
        headers=bearer(alice, **{"Idempotency-Key": f"forged-{forged_field}"}),
        json=forged,
    )

    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "SCHEMA_VALIDATION_FAILED"
    assert table_counts(database) == before


def test_malformed_json_and_invalid_key_fail_closed_without_transport_state(
    client: TestClient,
    database: Database,
) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    before = table_counts(database)

    malformed = client.post(
        "/api/v1/messages",
        headers=bearer(alice, **{"Idempotency-Key": "malformed-json"}),
        content=b'{"to": [',
    )
    invalid_key = client.post(
        "/api/v1/messages",
        headers={"Authorization": "Bearer agt_invalid_key_material"},
        json=payload(bob),
    )

    assert malformed.status_code == 422
    assert malformed.json()["error"]["code"] == "SCHEMA_VALIDATION_FAILED"
    assert invalid_key.status_code == 401
    assert invalid_key.json()["error"]["code"] == "INVALID_API_KEY"
    assert table_counts(database) == before


def test_eve_cannot_read_message_thread_or_attachment(client: TestClient) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    eve = register(client, "eve@agents.local")
    uploaded = client.post(
        "/api/v1/attachments",
        headers=bearer(alice),
        files={"file": ("secret.txt", b"private attachment canary", "text/plain")},
    )
    assert uploaded.status_code == 201, uploaded.text
    attachment_id = uploaded.json()["id"]
    accepted = client.post(
        "/api/v1/messages",
        headers=bearer(alice, **{"Idempotency-Key": "eve-isolation"}),
        json=payload(bob, attachments=[attachment_id]),
    )
    assert accepted.status_code == 201, accepted.text
    message = accepted.json()

    hidden_message = client.get(f"/api/v1/messages/{message['message_id']}", headers=bearer(eve))
    hidden_thread = client.get(f"/api/v1/threads/{message['thread_id']}", headers=bearer(eve))
    hidden_attachment = client.get(f"/api/v1/attachments/{attachment_id}", headers=bearer(eve))
    assert hidden_message.status_code == 404
    assert hidden_message.json()["error"]["code"] == "MESSAGE_NOT_FOUND"
    assert hidden_thread.status_code == 404
    assert hidden_thread.json()["error"]["code"] == "THREAD_NOT_FOUND"
    assert hidden_attachment.status_code == 404
    assert hidden_attachment.json()["error"]["code"] == "ATTACHMENT_NOT_FOUND"
    assert client.get("/api/v1/inbox", headers=bearer(eve)).json()["items"] == []


def test_request_logs_never_include_api_key_or_message_canaries(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    secret_key = alice["api_key"]
    idempotency_canary = "IDEMPOTENCY_LOG_CANARY_5a46"
    subject_canary = "SUBJECT_LOG_CANARY_d518"
    body_canary = "BODY_LOG_CANARY_ab09"
    caplog.clear()
    caplog.set_level(logging.INFO, logger="agentpost.http")

    response = send(
        client,
        alice,
        bob,
        key=idempotency_canary,
        subject=subject_canary,
        body=body_canary,
    )

    assert response.status_code == 201, response.text
    serialized = "\n".join(
        json.dumps(
            {
                "name": record.name,
                "message": record.getMessage(),
                "attributes": record.__dict__,
            },
            default=str,
            sort_keys=True,
        )
        for record in caplog.records
    )
    assert "request.completed" in serialized
    for sentinel in (secret_key, idempotency_canary, subject_canary, body_canary):
        assert sentinel not in serialized
    # Positive proof that the log still carries useful correlation dimensions.
    assert response.headers["X-Request-ID"] in serialized
    assert response.json()["message_id"] in serialized
    assert str(UUID(response.json()["thread_id"])) in serialized
