from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from agentpost.attachments.models import Attachment
from agentpost.config import Settings
from agentpost.db import Base, Database
from agentpost.main import create_app
from agentpost.messaging.models import Message


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
    uploader: dict[str, Any],
    *,
    filename: str = "report.txt",
    content: bytes = b"attachment content",
    content_type: str = "text/plain",
):
    return client.post(
        "/api/v1/attachments",
        headers=bearer(uploader),
        files={"file": (filename, content, content_type)},
    )


def message_payload(
    recipient: dict[str, Any] | str,
    *,
    attachments: list[str] | None = None,
    message_type: str = "message",
) -> dict[str, Any]:
    address = recipient if isinstance(recipient, str) else recipient["agent"]["address"]
    payload: dict[str, Any] = {
        "to": [{"address": address}],
        "type": message_type,
        "subject": "Attachment delivery",
        "content": {"format": "text", "body": "See the private attachment."},
        "attachments": attachments or [],
        "priority": "normal",
        "requires_ack": True,
        "metadata": {},
        "expires_at": None,
    }
    if message_type == "task":
        payload["task"] = {
            "instruction": "Review the attachment",
            "deadline": None,
            "expected_output": "markdown report",
        }
    return payload


def send(
    client: TestClient,
    sender: dict[str, Any],
    recipient: dict[str, Any] | str,
    *,
    key: str,
    attachments: list[str] | None = None,
    message_type: str = "message",
):
    return client.post(
        "/api/v1/messages",
        headers=bearer(sender, **{"Idempotency-Key": key}),
        json=message_payload(
            recipient,
            attachments=attachments,
            message_type=message_type,
        ),
    )


def attachment_row(database: Database, attachment_id: str) -> Attachment:
    with database.session_factory() as session:
        row = session.get(Attachment, UUID(attachment_id))
        assert row is not None
        session.expunge(row)
        return row


def attachment_count(database: Database) -> int:
    with database.session_factory() as session:
        return int(session.scalar(select(func.count()).select_from(Attachment)) or 0)


def message_count(database: Database) -> int:
    with database.session_factory() as session:
        return int(session.scalar(select(func.count()).select_from(Message)) or 0)


def storage_files(root: Path) -> set[Path]:
    if not root.exists():
        return set()
    return {path.relative_to(root) for path in root.rglob("*") if path.is_file()}


def assert_safe_metadata(
    metadata: dict[str, Any],
    *,
    raw_content: bytes | None = None,
    message_projection: bool = False,
) -> None:
    common_fields = {"id", "filename", "content_type", "size", "sha256"}
    expected_fields = (
        common_fields if message_projection else common_fields | {"state", "created_at"}
    )
    assert set(metadata) == expected_fields
    serialized = json.dumps(metadata, sort_keys=True)
    for forbidden in ("storage_key", "storage_path", "filesystem_path", ".tmp", "/objects/"):
        assert forbidden not in serialized
    if raw_content is not None:
        decoded = raw_content.decode("utf-8", errors="ignore")
        if decoded:
            assert decoded not in serialized


def assert_attachment_not_found(response: Any) -> None:
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "ATTACHMENT_NOT_FOUND"


def test_upload_computes_metadata_and_pending_download_is_owner_only(
    client: TestClient,
    database: Database,
) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    raw = b"unique-private-pending-bytes-57a6"

    missing_auth = client.post(
        "/api/v1/attachments",
        files={"file": ("secret.txt", raw, "text/plain")},
    )
    assert missing_auth.status_code == 401

    response = upload(
        client,
        alice,
        filename="private-report.txt",
        content=raw,
        content_type="text/plain",
    )
    assert response.status_code == 201, response.text
    metadata = response.json()
    assert_safe_metadata(metadata, raw_content=raw)
    assert metadata["filename"] == "private-report.txt"
    assert metadata["content_type"] == "text/plain"
    assert metadata["size"] == len(raw)
    assert metadata["sha256"] == hashlib.sha256(raw).hexdigest()
    assert metadata["state"] == "pending"

    stored = attachment_row(database, metadata["id"])
    assert str(stored.uploader_agent_id) == alice["agent"]["id"]
    assert stored.size == len(raw)
    assert stored.sha256 == hashlib.sha256(raw).hexdigest()
    assert stored.state == "pending"
    assert stored.message_id is None
    assert stored.storage_key
    assert stored.storage_key not in response.text

    unauthenticated = client.get(f"/api/v1/attachments/{metadata['id']}")
    assert unauthenticated.status_code == 401
    assert_attachment_not_found(
        client.get(
            f"/api/v1/attachments/{metadata['id']}",
            headers=bearer(bob),
        )
    )

    downloaded = client.get(
        f"/api/v1/attachments/{metadata['id']}",
        headers=bearer(alice),
    )
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.content == raw
    assert downloaded.headers["content-type"] == "application/octet-stream"
    assert downloaded.headers["x-content-type-options"] == "nosniff"
    disposition = downloaded.headers["content-disposition"]
    assert disposition.lower().startswith("attachment")
    assert "private-report.txt" in disposition
    assert stored.storage_key not in str(downloaded.headers)


@pytest.mark.parametrize(
    "unsafe_filename",
    [
        "../escape.txt",
        "folder/escape.txt",
        "/absolute.txt",
        "folder\\escape.txt",
        "C:\\absolute.txt",
        ".",
        "..",
        "nul\x00byte.txt",
        "header\r\nX-Injected: true.txt",
    ],
)
def test_unsafe_filename_is_rejected_or_safely_normalized_by_multipart_boundary(
    client: TestClient,
    database: Database,
    settings: Settings,
    unsafe_filename: str,
) -> None:
    alice = register(client, "alice@agents.local")
    before_files = storage_files(settings.storage_path)

    response = upload(
        client,
        alice,
        filename=unsafe_filename,
        content=b"must-not-persist",
    )

    if response.status_code in {400, 422}:
        assert attachment_count(database) == 0
        assert storage_files(settings.storage_path) == before_files
        return

    # Some multipart parsers normalize browser-style client paths and percent-escape
    # control characters before application validation. Such accepted names must be
    # demonstrably safe at both the metadata and response-header boundaries.
    assert response.status_code == 201, response.text
    metadata = response.json()
    normalized = metadata["filename"]
    assert normalized not in {".", ".."}
    assert not Path(normalized).is_absolute()
    assert all(character not in normalized for character in ("/", "\\", "\x00", "\r", "\n"))
    assert_safe_metadata(metadata, raw_content=b"must-not-persist")
    downloaded = client.get(f"/api/v1/attachments/{metadata['id']}", headers=bearer(alice))
    assert downloaded.status_code == 200, downloaded.text
    disposition = downloaded.headers["content-disposition"]
    assert "\r" not in disposition and "\n" not in disposition


def test_actual_oversized_stream_returns_413_and_cleans_temporary_files(
    database: Database,
    settings: Settings,
) -> None:
    constrained = Settings(
        environment="test",
        database_url=settings.database_url,
        storage_path=settings.storage_path,
        api_key_pepper=settings.api_key_pepper,
        cursor_secret=settings.cursor_secret,
        max_attachment_bytes=8,
        log_level="WARNING",
    )
    app = create_app(settings=constrained, database=database)
    with TestClient(app) as constrained_client:
        alice = register(constrained_client, "alice@agents.local")
        before_files = storage_files(settings.storage_path)
        response = upload(
            constrained_client,
            alice,
            filename="too-large.bin",
            content=b"123456789",
            content_type="application/octet-stream",
        )

    assert response.status_code == 413, response.text
    assert response.json()["error"]["code"] == "ATTACHMENT_TOO_LARGE"
    assert attachment_count(database) == 0
    assert storage_files(settings.storage_path) == before_files
    temporary_root = settings.storage_path / ".tmp"
    assert not temporary_root.exists() or not any(temporary_root.iterdir())


def test_binding_is_owner_only_single_use_and_attached_download_is_participant_only(
    client: TestClient,
    database: Database,
) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    eve = register(client, "eve@agents.local")
    alice_upload = upload(client, alice, filename="alice.txt", content=b"alice file").json()
    bob_upload = upload(client, bob, filename="bob.txt", content=b"bob file").json()

    cross_owner = send(
        client,
        alice,
        bob,
        key="cross-owner-attachment",
        attachments=[bob_upload["id"]],
    )
    assert cross_owner.status_code == 409, cross_owner.text
    assert cross_owner.json()["error"]["code"] == "ATTACHMENT_UNAVAILABLE"
    assert message_count(database) == 0
    unavailable_row = attachment_row(database, bob_upload["id"])
    assert unavailable_row.state == "pending"
    assert unavailable_row.message_id is None

    accepted = send(
        client,
        alice,
        bob,
        key="bind-alice-attachment",
        attachments=[alice_upload["id"]],
    )
    assert accepted.status_code == 201, accepted.text
    message = accepted.json()
    assert len(message["attachments"]) == 1
    attached_metadata = message["attachments"][0]
    assert_safe_metadata(
        attached_metadata,
        raw_content=b"alice file",
        message_projection=True,
    )
    assert attached_metadata["id"] == alice_upload["id"]
    attached_row = attachment_row(database, alice_upload["id"])
    assert attached_row.state == "attached"
    assert attached_row.message_id == message["message_id"]

    replay = send(
        client,
        alice,
        bob,
        key="bind-alice-attachment",
        attachments=[alice_upload["id"]],
    )
    assert replay.status_code == 200, replay.text
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert replay.json()["message_id"] == message["message_id"]

    second_bind = send(
        client,
        alice,
        bob,
        key="bind-alice-attachment-again",
        attachments=[alice_upload["id"]],
    )
    assert second_bind.status_code == 409, second_bind.text
    assert second_bind.json()["error"]["code"] == "ATTACHMENT_UNAVAILABLE"
    assert message_count(database) == 1

    for participant in (alice, bob):
        download = client.get(
            f"/api/v1/attachments/{alice_upload['id']}",
            headers=bearer(participant),
        )
        assert download.status_code == 200, download.text
        assert download.content == b"alice file"
    assert_attachment_not_found(
        client.get(
            f"/api/v1/attachments/{alice_upload['id']}",
            headers=bearer(eve),
        )
    )


def test_failed_send_leaves_pending_attachment_reusable_and_unbound(
    client: TestClient,
    database: Database,
) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    pending = upload(client, alice, filename="retry.txt", content=b"retry later").json()

    failed = send(
        client,
        alice,
        "missing@agents.local",
        key="failed-recipient-with-attachment",
        attachments=[pending["id"]],
    )
    assert failed.status_code == 404, failed.text
    assert message_count(database) == 0
    after_failure = attachment_row(database, pending["id"])
    assert after_failure.state == "pending"
    assert after_failure.message_id is None

    recovered = send(
        client,
        alice,
        bob,
        key="reuse-after-failed-send",
        attachments=[pending["id"]],
    )
    assert recovered.status_code == 201, recovered.text
    assert recovered.json()["attachments"][0]["id"] == pending["id"]
    assert attachment_row(database, pending["id"]).message_id == recovered.json()["message_id"]


def test_pending_and_attached_objects_survive_full_app_recreation(tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'restart.db'}"
    settings = Settings(
        environment="test",
        database_url=database_url,
        storage_path=tmp_path / "private-attachments",
        api_key_pepper="restart-test-pepper",
        cursor_secret="restart-cursor-secret",
        log_level="WARNING",
    )
    first_database = Database(database_url)
    Base.metadata.create_all(first_database.engine)
    raw = b"survives-complete-app-recreation"
    with TestClient(create_app(settings=settings, database=first_database)) as first_client:
        alice = register(first_client, "alice@agents.local")
        bob = register(first_client, "bob@agents.local")
        uploaded = upload(
            first_client,
            alice,
            filename="durable.bin",
            content=raw,
            content_type="application/octet-stream",
        ).json()

    second_database = Database(database_url)
    with TestClient(create_app(settings=settings, database=second_database)) as second_client:
        pending_download = second_client.get(
            f"/api/v1/attachments/{uploaded['id']}", headers=bearer(alice)
        )
        assert pending_download.status_code == 200, pending_download.text
        assert pending_download.content == raw
        accepted = send(
            second_client,
            alice,
            bob,
            key="bind-after-first-restart",
            attachments=[uploaded["id"]],
        )
        assert accepted.status_code == 201, accepted.text
        message_id = accepted.json()["message_id"]

    third_database = Database(database_url)
    with TestClient(create_app(settings=settings, database=third_database)) as third_client:
        attached_download = third_client.get(
            f"/api/v1/attachments/{uploaded['id']}", headers=bearer(bob)
        )
        assert attached_download.status_code == 200, attached_download.text
        assert attached_download.content == raw
        visible_message = third_client.get(f"/api/v1/messages/{message_id}", headers=bearer(bob))
        assert visible_message.status_code == 200, visible_message.text
        assert visible_message.json()["attachments"][0]["id"] == uploaded["id"]


def test_result_reply_can_bind_analysis_attachment_for_original_task_sender(
    client: TestClient,
    database: Database,
) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    eve = register(client, "eve@agents.local")
    original = send(
        client,
        alice,
        bob,
        key="task-awaiting-result-attachment",
        message_type="task",
    )
    assert original.status_code == 201, original.text
    analysis_bytes = b"# Completed analysis\n\nPrivate result."
    analysis = upload(
        client,
        bob,
        filename="analysis.md",
        content=analysis_bytes,
        content_type="text/markdown",
    ).json()

    reply = client.post(
        f"/api/v1/messages/{original.json()['message_id']}/reply",
        headers=bearer(bob, **{"Idempotency-Key": "result-with-analysis-attachment"}),
        json={
            "type": "result",
            "subject": "Analysis complete",
            "content": {"format": "markdown", "body": "The analysis is attached."},
            "result": {"status": "completed", "summary": "Completed safely"},
            "attachments": [analysis["id"]],
            "priority": "normal",
            "requires_ack": True,
            "metadata": {},
            "expires_at": None,
        },
    )
    assert reply.status_code == 201, reply.text
    reply_message = reply.json()
    assert reply_message["type"] == "result"
    assert reply_message["reply_to"] == original.json()["message_id"]
    assert reply_message["thread_id"] == original.json()["thread_id"]
    assert reply_message["attachments"][0]["id"] == analysis["id"]
    assert_safe_metadata(
        reply_message["attachments"][0],
        raw_content=analysis_bytes,
        message_projection=True,
    )
    assert attachment_row(database, analysis["id"]).message_id == reply_message["message_id"]

    alice_download = client.get(f"/api/v1/attachments/{analysis['id']}", headers=bearer(alice))
    assert alice_download.status_code == 200, alice_download.text
    assert alice_download.content == analysis_bytes
    assert_attachment_not_found(
        client.get(f"/api/v1/attachments/{analysis['id']}", headers=bearer(eve))
    )
