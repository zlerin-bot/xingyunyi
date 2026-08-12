from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from agentpost.attachments.models import Attachment
from agentpost.config import Settings
from agentpost.db import Base, Database
from agentpost.main import create_app
from agentpost.messaging.models import Delivery, Message


def register(client: TestClient, address: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/agents",
        json={"address": address, "display_name": address.partition("@")[0].title()},
    )
    assert response.status_code == 201, response.text
    return response.json()


def bearer(registration: dict[str, Any], **extra: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {registration['api_key']}", **extra}


def upload(
    client: TestClient,
    owner: dict[str, Any],
    *,
    filename: str,
    body: bytes,
    content_type: str,
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/attachments",
        headers=bearer(owner),
        files={"file": (filename, body, content_type)},
    )
    assert response.status_code == 201, response.text
    return response.json()


def new_client(settings: Settings) -> tuple[Database, TestClient]:
    database = Database(settings.database_url)
    return database, TestClient(create_app(settings=settings, database=database))


@pytest.mark.e2e
def test_offline_task_result_attachments_survive_two_full_restarts(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'offline-e2e.db'}"
    settings = Settings(
        environment="test",
        database_url=database_url,
        storage_path=tmp_path / "attachments",
        api_key_pepper="offline-e2e-pepper",
        cursor_secret="offline-e2e-cursor-secret",
        log_level="WARNING",
    )
    bootstrap = Database(database_url)
    Base.metadata.create_all(bootstrap.engine)
    bootstrap.dispose()

    report_bytes = b"%PDF-1.4\nagentpost durable report\n%%EOF\n"
    analysis_bytes = b"# Analysis\n\nThe report was processed while Alice was offline.\n"

    # Phase 1: Bob exists but no Bob client action occurs while Alice sends the task.
    first_database, first_client = new_client(settings)
    with first_client:
        alice = register(first_client, "alice@agents.local")
        bob = register(first_client, "bob@agents.local")
        report = upload(
            first_client,
            alice,
            filename="report.pdf",
            body=report_bytes,
            content_type="application/pdf",
        )
        accepted = first_client.post(
            "/api/v1/messages",
            headers=bearer(alice, **{"Idempotency-Key": "offline-task-e2e"}),
            json={
                "to": [{"address": bob["agent"]["address"]}],
                "type": "task",
                "subject": "Analyse report.pdf",
                "content": {"format": "text", "body": "Analyse the attached report"},
                "task": {
                    "instruction": "Analyse the attached report",
                    "deadline": None,
                    "expected_output": "markdown report",
                },
                "attachments": [report["id"]],
                "priority": "normal",
                "requires_ack": True,
                "metadata": {"scenario": "offline-e2e"},
                "expires_at": None,
            },
        )
        assert accepted.status_code == 201, accepted.text
        task = accepted.json()
        task_id = task["message_id"]
        thread_id = task["thread_id"]
        assert task["delivery"]["status"] == "delivered"
        assert task["attachments"][0]["id"] == report["id"]
    # The TestClient lifespan disposes the first Database/engine: this is a full app restart.

    # Phase 2: Bob starts later, reads/ACKs, and replies while Alice performs no action.
    second_database, second_client = new_client(settings)
    with second_client:
        unread = second_client.get(
            "/api/v1/inbox",
            params={"status": "unread"},
            headers=bearer(bob),
        )
        assert unread.status_code == 200, unread.text
        assert [item["message_id"] for item in unread.json()["items"]] == [task_id]
        received_task = unread.json()["items"][0]
        assert received_task["type"] == "task"
        assert received_task["content"]["security_label"] == "external_agent_content"

        report_download = second_client.get(
            f"/api/v1/attachments/{report['id']}",
            headers=bearer(bob),
        )
        assert report_download.status_code == 200, report_download.text
        assert report_download.content == report_bytes

        read = second_client.post(
            f"/api/v1/messages/{task_id}/read",
            headers=bearer(bob),
        )
        ack = second_client.post(
            f"/api/v1/messages/{task_id}/ack",
            headers=bearer(bob),
        )
        assert read.status_code == ack.status_code == 200
        assert read.json()["delivery"]["status"] == "read"
        assert ack.json()["delivery"]["status"] == "acked"

        analysis = upload(
            second_client,
            bob,
            filename="analysis.md",
            body=analysis_bytes,
            content_type="text/markdown",
        )
        reply = second_client.post(
            f"/api/v1/messages/{task_id}/reply",
            headers=bearer(bob, **{"Idempotency-Key": "offline-result-e2e"}),
            json={
                "type": "result",
                "subject": "Report analysis completed",
                "content": {"format": "markdown", "body": analysis_bytes.decode()},
                "result": {"status": "completed", "summary": "Analysis attached"},
                "attachments": [analysis["id"]],
                "priority": "normal",
                "requires_ack": True,
                "metadata": {},
                "expires_at": None,
            },
        )
        assert reply.status_code == 201, reply.text
        result = reply.json()
        result_id = result["message_id"]
        assert result["reply_to"] == task_id
        assert result["thread_id"] == thread_id
        assert result["attachments"][0]["id"] == analysis["id"]

        sender_view = second_client.get(
            f"/api/v1/messages/{task_id}",
            headers=bearer(alice),
        )
        assert sender_view.status_code == 200
        assert sender_view.json()["delivery"]["status"] == "acked"

    # Phase 3: Alice starts later and retrieves the durable result and its file.
    third_database, third_client = new_client(settings)
    with third_client:
        alice_unread = third_client.get(
            "/api/v1/inbox",
            params={"status": "unread", "type": "result"},
            headers=bearer(alice),
        )
        assert alice_unread.status_code == 200, alice_unread.text
        assert [item["message_id"] for item in alice_unread.json()["items"]] == [result_id]
        result_message = alice_unread.json()["items"][0]
        assert result_message["result"]["status"] == "completed"
        assert result_message["reply_to"] == task_id

        analysis_download = third_client.get(
            f"/api/v1/attachments/{analysis['id']}",
            headers=bearer(alice),
        )
        assert analysis_download.status_code == 200, analysis_download.text
        assert analysis_download.content == analysis_bytes

        history = third_client.get(
            f"/api/v1/threads/{thread_id}",
            headers=bearer(alice),
        )
        assert history.status_code == 200, history.text
        assert [item["message_id"] for item in history.json()["messages"]] == [
            task_id,
            result_id,
        ]
        assert (
            third_client.post(
                f"/api/v1/messages/{result_id}/read", headers=bearer(alice)
            ).status_code
            == 200
        )
        final_ack = third_client.post(f"/api/v1/messages/{result_id}/ack", headers=bearer(alice))
        assert final_ack.status_code == 200
        assert final_ack.json()["delivery"]["status"] == "acked"

        with third_database.session_factory() as session:
            assert session.scalar(select(func.count()).select_from(Message)) == 2
            assert session.scalar(select(func.count()).select_from(Delivery)) == 2
            assert session.scalar(select(func.count()).select_from(Attachment)) == 2
            assert all(
                attachment.message_id is not None
                for attachment in session.scalars(select(Attachment))
            )
