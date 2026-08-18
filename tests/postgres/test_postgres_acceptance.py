from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event
from typing import Any

import pytest
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select, text

from agentpost.config import Settings
from agentpost.control.models import AgentOwnership
from agentpost.db import Database
from agentpost.identity.models import Agent, AgentApiKey
from agentpost.main import create_app
from agentpost.messaging.models import AuditLog, Delivery, IdempotencyRecord, Message
from agentpost.onboarding.models import (
    AgentConnectorBinding,
    AgentPairingSession,
    ConnectorInstance,
)

pytestmark = pytest.mark.postgres
ADMIN_KEY = "postgres-admin-secret-postgres-admin-secret"


def _settings(database_url: str, storage_path: Path) -> Settings:
    return Settings(
        environment="test",
        database_url=database_url,
        storage_path=storage_path,
        api_key_pepper="postgres-acceptance-pepper",
        human_api_key_pepper="postgres-human-pepper",
        cursor_secret="postgres-acceptance-cursor",
        pairing_secret="postgres-pairing-secret",
        pairing_enabled=True,
        managed_agent_domain="agents.local",
        public_base_url="https://agentpost.test",
        admin_token=ADMIN_KEY,
        log_level="WARNING",
    )


def _register(client: TestClient, address: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/agents",
        json={"address": address, "display_name": address.partition("@")[0]},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _headers(agent: dict[str, Any], *, key: str | None = None) -> dict[str, str]:
    result = {"Authorization": f"Bearer {agent['api_key']}"}
    if key is not None:
        result["Idempotency-Key"] = key
    return result


def _payload(recipient: str, *, body: str = "Hello Bob") -> dict[str, Any]:
    return {
        "to": [{"address": recipient}],
        "type": "message",
        "subject": "PostgreSQL durability acceptance",
        "content": {"format": "text", "body": body},
        "attachments": [],
        "priority": "normal",
        "requires_ack": True,
        "metadata": {},
        "expires_at": None,
    }


def _send(
    client: TestClient,
    sender: dict[str, Any],
    recipient: str,
    *,
    key: str,
    body: str = "Hello Bob",
):
    return client.post(
        "/api/v1/messages",
        headers=_headers(sender, key=key),
        json=_payload(recipient, body=body),
    )


def _reply_payload(body: str = "Received") -> dict[str, Any]:
    return {
        "type": "response",
        "subject": "Received",
        "content": {"format": "text", "body": body},
        "attachments": [],
        "priority": "normal",
        "requires_ack": True,
        "metadata": {},
        "expires_at": None,
    }


def _count(database: Database, model: type[Any]) -> int:
    with database.session_factory() as session:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)


def test_alembic_upgrade_reaches_single_head_and_creates_expected_schema(
    migrated_database: Database,
) -> None:
    script = ScriptDirectory(str(Path(__file__).resolve().parents[2] / "migrations"))
    expected_head = script.get_current_head()
    assert expected_head is not None

    with migrated_database.engine.connect() as connection:
        actual_revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        table_names = set(inspect(connection).get_table_names())

    assert actual_revision == expected_head
    assert {
        "access_rules",
        "agents",
        "agent_api_keys",
        "attachments",
        "audit_logs",
        "deliveries",
        "idempotency_records",
        "messages",
        "agent_pairing_sessions",
        "connector_instances",
        "agent_connector_bindings",
    } <= table_names


@pytest.mark.e2e
@pytest.mark.concurrency
def test_postgres_pairing_is_atomic_idempotent_and_restart_durable(
    postgres_url: str,
    migrated_database: Database,
    tmp_path: Path,
) -> None:
    settings = _settings(postgres_url, tmp_path / "attachments")
    with TestClient(create_app(settings=settings, database=migrated_database)) as client:
        pairing_response = client.post(
            "/api/v1/connect/pairings",
            json={
                "connector_type": "codex",
                "display_name": "Codex PostgreSQL acceptance",
                "device_name": "test host",
                "capabilities": ["financial-research"],
            },
        )
        assert pairing_response.status_code == 201, pairing_response.text
        pairing = pairing_response.json()
        human_response = client.post(
            "/api/v1/admin/humans",
            headers={"Authorization": f"Bearer {ADMIN_KEY}"},
            json={"email": "pairing-owner@example.com", "display_name": "Pairing Owner"},
        )
        assert human_response.status_code == 201, human_response.text
        human = human_response.json()
        login = client.post(
            "/api/v1/orbit/session",
            headers={"Authorization": f"Bearer {human['access_key']}"},
        )
        assert login.status_code == 201, login.text
        csrf = login.json()["csrf_token"]
        confirmation = client.post(
            f"/api/v1/orbit/pairings/{pairing['pairing_id']}/confirmation",
            headers={
                "Authorization": f"Bearer {human['access_key']}",
                "X-CSRF-Token": csrf,
            },
            json={"intent": "approve", "user_code": pairing["user_code"]},
        )
        assert confirmation.status_code == 200, confirmation.text
        decision_workers = 8
        decision_barrier = Barrier(decision_workers)

        def concurrent_decision(_: int):
            decision_barrier.wait(timeout=10)
            return client.post(
                f"/api/v1/orbit/pairings/{pairing['pairing_id']}/decision",
                headers={
                    "Idempotency-Key": "postgres-pairing-decision",
                    "X-CSRF-Token": csrf,
                    "X-Human-Confirmation": confirmation.json()["confirmation_token"],
                },
                json={"decision": "approved", "local_agent_id": "postgres-pluto"},
            )

        with ThreadPoolExecutor(max_workers=decision_workers) as executor:
            decisions = list(executor.map(concurrent_decision, range(decision_workers)))
        assert [response.status_code for response in decisions] == [200] * decision_workers
        assert {response.json()["pairing"]["agent"]["id"] for response in decisions} == {
            decisions[0].json()["pairing"]["agent"]["id"]
        }

        claimed = client.post(
            "/api/v1/connect/pairings/token",
            json={"device_code": pairing["device_code"]},
        )
        assert claimed.status_code == 200, claimed.text
        connector_key = claimed.json()["api_key"]

    restarted_database = Database(postgres_url)
    try:
        with TestClient(create_app(settings=settings, database=restarted_database)) as restarted:
            inbox = restarted.get(
                "/api/v1/inbox?status=unread",
                headers={"Authorization": f"Bearer {connector_key}"},
            )
            assert inbox.status_code == 200, inbox.text
            assert inbox.json()["items"] == []
        assert _count(restarted_database, Agent) == 1
        assert _count(restarted_database, AgentOwnership) == 1
        assert _count(restarted_database, AgentPairingSession) == 1
        assert _count(restarted_database, ConnectorInstance) == 1
        assert _count(restarted_database, AgentConnectorBinding) == 1
        assert _count(restarted_database, AgentApiKey) == 1
    finally:
        restarted_database.dispose()


@pytest.mark.e2e
def test_offline_message_and_reply_survive_two_engine_and_app_recreations(
    postgres_url: str,
    migrated_database: Database,
    tmp_path: Path,
) -> None:
    settings = _settings(postgres_url, tmp_path / "attachments")
    first_database = migrated_database
    with TestClient(create_app(settings=settings, database=first_database)) as first_client:
        alice = _register(first_client, "alice@agents.local")
        bob = _register(first_client, "bob@agents.local")
        accepted = _send(
            first_client,
            alice,
            bob["agent"]["address"],
            key="postgres-offline-send",
        )
        assert accepted.status_code == 201, accepted.text
        original = accepted.json()
        original_id = original["message_id"]
        assert original["delivery"]["status"] == "delivered"

    second_database = Database(postgres_url)
    with TestClient(create_app(settings=settings, database=second_database)) as bob_client:
        unread = bob_client.get(
            "/api/v1/inbox",
            params={"status": "unread"},
            headers=_headers(bob),
        )
        assert unread.status_code == 200, unread.text
        assert [item["message_id"] for item in unread.json()["items"]] == [original_id]

        marked_read = bob_client.post(f"/api/v1/messages/{original_id}/read", headers=_headers(bob))
        assert marked_read.status_code == 200, marked_read.text
        assert marked_read.json()["delivery"]["status"] == "read"
        acked = bob_client.post(f"/api/v1/messages/{original_id}/ack", headers=_headers(bob))
        assert acked.status_code == 200, acked.text
        assert acked.json()["delivery"]["status"] == "acked"

        reply = bob_client.post(
            f"/api/v1/messages/{original_id}/reply",
            headers=_headers(bob, key="postgres-offline-reply"),
            json=_reply_payload(),
        )
        assert reply.status_code == 201, reply.text
        reply_id = reply.json()["message_id"]

    third_database = Database(postgres_url)
    with TestClient(create_app(settings=settings, database=third_database)) as alice_client:
        alice_inbox = alice_client.get(
            "/api/v1/inbox",
            params={"status": "unread"},
            headers=_headers(alice),
        )
        assert alice_inbox.status_code == 200, alice_inbox.text
        assert [item["message_id"] for item in alice_inbox.json()["items"]] == [reply_id]
        persisted_original = alice_client.get(
            f"/api/v1/messages/{original_id}", headers=_headers(alice)
        )
        assert persisted_original.status_code == 200, persisted_original.text
        assert persisted_original.json()["delivery"]["status"] == "acked"
        assert persisted_original.json()["delivery"]["acked_at"] is not None


@pytest.mark.concurrency
def test_postgres_concurrency_exactly_deduplicates_transitions_and_100_senders(
    postgres_url: str,
    migrated_database: Database,
    tmp_path: Path,
) -> None:
    settings = _settings(postgres_url, tmp_path / "attachments")
    with TestClient(create_app(settings=settings, database=migrated_database)) as client:
        alice = _register(client, "alice@agents.local")
        bob = _register(client, "bob@agents.local")

        duplicate_workers = 12
        duplicate_barrier = Barrier(duplicate_workers)

        def duplicate_send(_: int):
            duplicate_barrier.wait(timeout=10)
            return _send(
                client,
                alice,
                bob["agent"]["address"],
                key="postgres-concurrent-idempotency",
                body="identical payload",
            )

        with ThreadPoolExecutor(max_workers=duplicate_workers) as executor:
            duplicate_responses = list(executor.map(duplicate_send, range(duplicate_workers)))

        statuses = sorted(response.status_code for response in duplicate_responses)
        assert statuses == [200] * (duplicate_workers - 1) + [201]
        duplicate_ids = {response.json()["message_id"] for response in duplicate_responses}
        assert len(duplicate_ids) == 1

        transition_message = _send(
            client,
            alice,
            bob["agent"]["address"],
            key="postgres-concurrent-transition-parent",
        )
        assert transition_message.status_code == 201, transition_message.text
        transition_id = transition_message.json()["message_id"]
        transition_workers = 12
        transition_barrier = Barrier(transition_workers)

        def concurrent_ack(_: int):
            transition_barrier.wait(timeout=10)
            return client.post(f"/api/v1/messages/{transition_id}/ack", headers=_headers(bob))

        with ThreadPoolExecutor(max_workers=transition_workers) as executor:
            transition_responses = list(executor.map(concurrent_ack, range(transition_workers)))
        assert [response.status_code for response in transition_responses] == [200] * 12

        senders = [_register(client, f"sender-{index:03d}@agents.local") for index in range(100)]
        baseline_messages = _count(migrated_database, Message)
        baseline_deliveries = _count(migrated_database, Delivery)
        baseline_idempotency = _count(migrated_database, IdempotencyRecord)
        start = Event()

        def burst_send(index: int):
            assert start.wait(timeout=10)
            return _send(
                client,
                senders[index],
                bob["agent"]["address"],
                key=f"postgres-burst-{index:03d}",
                body=f"concurrent message {index:03d}",
            )

        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = [executor.submit(burst_send, index) for index in range(100)]
            start.set()
            burst_responses = [future.result(timeout=60) for future in futures]
        assert [response.status_code for response in burst_responses] == [201] * 100
        assert len({response.json()["message_id"] for response in burst_responses}) == 100

    verification_database = Database(postgres_url)
    try:
        assert _count(verification_database, Message) == baseline_messages + 100
        assert _count(verification_database, Delivery) == baseline_deliveries + 100
        assert _count(verification_database, IdempotencyRecord) == baseline_idempotency + 100
        with verification_database.session_factory() as session:
            duplicate_records = int(
                session.scalar(
                    select(func.count())
                    .select_from(IdempotencyRecord)
                    .where(IdempotencyRecord.idempotency_key == "postgres-concurrent-idempotency")
                )
                or 0
            )
            ack_audits = int(
                session.scalar(
                    select(func.count())
                    .select_from(AuditLog)
                    .where(
                        AuditLog.action == "message.ack",
                        AuditLog.target_id == transition_id,
                    )
                )
                or 0
            )
        assert duplicate_records == 1
        assert ack_audits == 1
    finally:
        verification_database.dispose()
