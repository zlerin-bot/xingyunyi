from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from agentpost.db import Database
from agentpost.messaging.models import AuditLog, Delivery


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


def send_message(
    client: TestClient,
    sender: dict[str, Any],
    recipient: dict[str, Any],
    *,
    key: str,
    requires_ack: bool = True,
    subject: str = "Lifecycle test",
    body: str = "Untrusted lifecycle test body",
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/messages",
        headers=bearer(sender, **{"Idempotency-Key": key}),
        json={
            "to": [{"address": recipient["agent"]["address"]}],
            "type": "message",
            "subject": subject,
            "content": {"format": "text", "body": body},
            "attachments": [],
            "priority": "normal",
            "requires_ack": requires_ack,
            "metadata": {},
            "expires_at": None,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def transition(
    client: TestClient,
    registration: dict[str, Any],
    message_id: str,
    action: str,
    *,
    request_id: str | None = None,
):
    extra = {"X-Request-ID": request_id} if request_id else {}
    return client.post(
        f"/api/v1/messages/{message_id}/{action}",
        headers=bearer(registration, **extra),
    )


def delivery(resource: dict[str, Any]) -> dict[str, Any]:
    value = resource["delivery"]
    assert isinstance(value, dict)
    return value


def inbox_ids(
    client: TestClient,
    registration: dict[str, Any],
    *,
    status: str | None = None,
) -> set[str]:
    params = {"status": status} if status is not None else None
    response = client.get(
        "/api/v1/inbox",
        params=params,
        headers=bearer(registration),
    )
    assert response.status_code == 200, response.text
    return {str(item["message_id"]) for item in response.json()["items"]}


def audit_rows(database: Database, message_id: str) -> list[AuditLog]:
    with database.session_factory() as session:
        return list(
            session.scalars(
                select(AuditLog)
                .where(AuditLog.target_type == "message", AuditLog.target_id == message_id)
                .order_by(AuditLog.created_at, AuditLog.action)
            )
        )


def transition_audit_count(database: Database, message_id: str, action: str) -> int:
    return sum(row.action == f"message.{action}" for row in audit_rows(database, message_id))


def stored_delivery(database: Database, message_id: str) -> Delivery:
    with database.session_factory() as session:
        value = session.scalar(select(Delivery).where(Delivery.message_id == message_id))
        assert value is not None
        session.expunge(value)
        return value


def assert_not_found(response: Any, *, request_id: str) -> None:
    assert response.status_code == 404, response.text
    assert response.headers["X-Request-ID"] == request_id
    assert response.json() == {
        "error": {
            "code": "MESSAGE_NOT_FOUND",
            "message": "Message was not found",
            "request_id": request_id,
            "details": {},
        }
    }


@pytest.mark.parametrize("action", ["read", "ack"])
def test_only_recipient_can_transition_sender_and_eve_receive_hidden_not_found(
    client: TestClient,
    database: Database,
    action: str,
) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    eve = register(client, "eve@agents.local")
    message = send_message(
        client,
        alice,
        bob,
        key=f"recipient-only-{action}",
    )
    message_id = message["message_id"]

    sender_attempt = transition(
        client,
        alice,
        message_id,
        action,
        request_id=f"sender-cannot-{action}",
    )
    eve_attempt = transition(
        client,
        eve,
        message_id,
        action,
        request_id=f"eve-cannot-{action}",
    )

    assert_not_found(sender_attempt, request_id=f"sender-cannot-{action}")
    assert_not_found(eve_attempt, request_id=f"eve-cannot-{action}")
    visible_to_sender = client.get(
        f"/api/v1/messages/{message_id}",
        headers=bearer(alice),
    )
    assert visible_to_sender.status_code == 200, visible_to_sender.text
    assert delivery(visible_to_sender.json()) == delivery(message)
    persisted = stored_delivery(database, message_id)
    assert persisted.delivery_status == "delivered"
    assert persisted.read_at is None
    assert persisted.acked_at is None
    assert transition_audit_count(database, message_id, action) == 0


def test_get_message_and_inbox_have_no_lifecycle_side_effects(
    client: TestClient,
    database: Database,
) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    message = send_message(client, alice, bob, key="get-no-transition")
    message_id = message["message_id"]

    for registration in (alice, bob):
        fetched = client.get(
            f"/api/v1/messages/{message_id}",
            headers=bearer(registration),
        )
        assert fetched.status_code == 200, fetched.text
    assert message_id in inbox_ids(client, bob)
    assert message_id in inbox_ids(client, bob, status="unread")

    persisted = stored_delivery(database, message_id)
    assert persisted.delivery_status == "delivered"
    assert persisted.read_at is None
    assert persisted.acked_at is None
    assert transition_audit_count(database, message_id, "read") == 0
    assert transition_audit_count(database, message_id, "ack") == 0


def test_read_is_monotonic_idempotent_and_preserves_first_timestamp(
    client: TestClient,
    database: Database,
) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    message = send_message(client, alice, bob, key="read-idempotent")
    message_id = message["message_id"]

    first = transition(client, bob, message_id, "read")
    repeated = transition(client, bob, message_id, "read")

    assert first.status_code == repeated.status_code == 200
    first_delivery = delivery(first.json())
    repeated_delivery = delivery(repeated.json())
    assert first_delivery["status"] == repeated_delivery["status"] == "read"
    assert first_delivery["read_at"] is not None
    assert first_delivery["read_at"] == repeated_delivery["read_at"]
    assert first_delivery.get("acked_at") is None
    assert repeated_delivery.get("acked_at") is None
    persisted = stored_delivery(database, message_id)
    assert persisted.delivery_status == "read"
    assert persisted.read_at is not None
    assert persisted.acked_at is None
    assert transition_audit_count(database, message_id, "read") == 1


def test_ack_from_delivered_atomically_sets_read_and_preserves_first_timestamps(
    client: TestClient,
    database: Database,
) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    message = send_message(client, alice, bob, key="ack-idempotent")
    message_id = message["message_id"]

    first = transition(client, bob, message_id, "ack")
    repeated = transition(client, bob, message_id, "ack")

    assert first.status_code == repeated.status_code == 200
    first_delivery = delivery(first.json())
    repeated_delivery = delivery(repeated.json())
    assert first_delivery["status"] == repeated_delivery["status"] == "acked"
    assert first_delivery["read_at"] is not None
    assert first_delivery["acked_at"] is not None
    assert datetime.fromisoformat(first_delivery["read_at"]) <= datetime.fromisoformat(
        first_delivery["acked_at"]
    )
    assert repeated_delivery["read_at"] == first_delivery["read_at"]
    assert repeated_delivery["acked_at"] == first_delivery["acked_at"]
    persisted = stored_delivery(database, message_id)
    assert persisted.delivery_status == "acked"
    assert persisted.read_at is not None
    assert persisted.acked_at is not None
    assert persisted.read_at <= persisted.acked_at
    assert transition_audit_count(database, message_id, "ack") == 1


def test_read_then_ack_preserves_read_time_and_sender_sees_final_state(
    client: TestClient,
    database: Database,
) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    message = send_message(client, alice, bob, key="read-then-ack")
    message_id = message["message_id"]

    read_response = transition(client, bob, message_id, "read")
    assert read_response.status_code == 200, read_response.text
    first_read_at = delivery(read_response.json())["read_at"]
    ack_response = transition(client, bob, message_id, "ack")
    assert ack_response.status_code == 200, ack_response.text
    ack_delivery = delivery(ack_response.json())
    assert ack_delivery["status"] == "acked"
    assert ack_delivery["read_at"] == first_read_at
    assert datetime.fromisoformat(first_read_at) <= datetime.fromisoformat(ack_delivery["acked_at"])

    sender_view = client.get(
        f"/api/v1/messages/{message_id}",
        headers=bearer(alice),
    )
    assert sender_view.status_code == 200, sender_view.text
    assert delivery(sender_view.json()) == ack_delivery
    assert transition_audit_count(database, message_id, "read") == 1
    assert transition_audit_count(database, message_id, "ack") == 1


def test_read_after_ack_does_not_regress_or_change_timestamps(
    client: TestClient,
    database: Database,
) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    message = send_message(client, alice, bob, key="ack-then-read")
    message_id = message["message_id"]

    ack_response = transition(client, bob, message_id, "ack")
    assert ack_response.status_code == 200, ack_response.text
    before = delivery(ack_response.json())
    read_response = transition(client, bob, message_id, "read")

    assert read_response.status_code == 200, read_response.text
    after = delivery(read_response.json())
    assert after["status"] == "acked"
    assert after["read_at"] == before["read_at"]
    assert after["acked_at"] == before["acked_at"]
    assert transition_audit_count(database, message_id, "ack") == 1
    assert transition_audit_count(database, message_id, "read") == 0


def test_requires_ack_false_does_not_forbid_explicit_ack(
    client: TestClient,
    database: Database,
) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    message = send_message(
        client,
        alice,
        bob,
        key="optional-ack",
        requires_ack=False,
    )
    assert message["requires_ack"] is False

    response = transition(client, bob, message["message_id"], "ack")

    assert response.status_code == 200, response.text
    assert delivery(response.json())["status"] == "acked"
    assert transition_audit_count(database, message["message_id"], "ack") == 1


@pytest.mark.parametrize("action", ["read", "ack"])
def test_concurrent_duplicate_transitions_are_consistent_and_audited_once(
    client: TestClient,
    database: Database,
    action: str,
) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    message = send_message(client, alice, bob, key=f"concurrent-{action}")
    message_id = message["message_id"]
    workers = 8
    start = Barrier(workers)

    def invoke(index: int):
        start.wait(timeout=5)
        return transition(
            client,
            bob,
            message_id,
            action,
            request_id=f"concurrent-{action}-{index}",
        )

    with ThreadPoolExecutor(max_workers=workers) as executor:
        responses = list(executor.map(invoke, range(workers)))

    assert [response.status_code for response in responses] == [200] * workers
    final = client.get(f"/api/v1/messages/{message_id}", headers=bearer(alice))
    assert final.status_code == 200, final.text
    final_delivery = delivery(final.json())
    expected_status = "read" if action == "read" else "acked"
    assert final_delivery["status"] == expected_status
    assert final_delivery["read_at"] is not None
    if action == "ack":
        assert final_delivery["acked_at"] is not None
        assert datetime.fromisoformat(final_delivery["read_at"]) <= datetime.fromisoformat(
            final_delivery["acked_at"]
        )
    else:
        assert final_delivery.get("acked_at") is None
    assert transition_audit_count(database, message_id, action) == 1


def test_inbox_status_and_unread_filters_track_explicit_lifecycle(
    client: TestClient,
) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    delivered_message = send_message(client, alice, bob, key="filter-delivered")
    read_message = send_message(client, alice, bob, key="filter-read")
    acked_message = send_message(client, alice, bob, key="filter-acked")
    read_id = read_message["message_id"]
    acked_id = acked_message["message_id"]
    assert transition(client, bob, read_id, "read").status_code == 200
    assert transition(client, bob, acked_id, "ack").status_code == 200

    assert inbox_ids(client, bob) == {
        delivered_message["message_id"],
        read_id,
        acked_id,
    }
    assert inbox_ids(client, bob, status="unread") == {delivered_message["message_id"]}
    assert inbox_ids(client, bob, status="delivered") == {delivered_message["message_id"]}
    assert inbox_ids(client, bob, status="read") == {read_id}
    assert inbox_ids(client, bob, status="acked") == {acked_id}


def test_audit_records_exclude_message_content_subject_and_credentials(
    client: TestClient,
    database: Database,
) -> None:
    subject = "SUBJECT_CANARY_96cbfe1a"
    body = "BODY_CANARY_8bd43ac7"
    idempotency_key = "IDEMPOTENCY_KEY_CANARY_393fa12e"
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    message = send_message(
        client,
        alice,
        bob,
        key=idempotency_key,
        subject=subject,
        body=body,
    )
    message_id = message["message_id"]
    assert transition(client, bob, message_id, "read").status_code == 200
    assert transition(client, bob, message_id, "ack").status_code == 200

    rows = audit_rows(database, message_id)
    assert {row.action for row in rows} == {
        "message.accepted",
        "message.read",
        "message.ack",
    }
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
    for secret in (
        subject,
        body,
        idempotency_key,
        alice["api_key"],
        bob["api_key"],
    ):
        assert secret not in serialized
