from __future__ import annotations

import json
import stat
from pathlib import Path
from typing import Any

import httpx
import pytest
from agentpost_sdk import (
    ConnectorCredential,
    ConnectorWorker,
    JsonCursorStore,
    KeyringCredentialStore,
    MemoryCursorStore,
)

from agentpost import AgentPost

NOW = "2026-08-18T08:00:00Z"
AGENT_ID = "10000000-0000-0000-0000-000000000001"
SENDER_ID = "20000000-0000-0000-0000-000000000002"
DELIVERY_ID = "30000000-0000-0000-0000-000000000003"
THREAD_ID = "40000000-0000-0000-0000-000000000004"


class FakeKeyring:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, account: str) -> str | None:
        return self.values.get((service, account))

    def set_password(self, service: str, account: str, value: str) -> None:
        self.values[(service, account)] = value

    def delete_password(self, service: str, account: str) -> None:
        self.values.pop((service, account), None)


class UnavailableKeyring:
    def get_password(self, _service: str, _account: str) -> str | None:
        raise RuntimeError("secret backend detail")


class MemoryCredentialStore:
    def __init__(self, credential: ConnectorCredential | None = None) -> None:
        self.credential = credential

    def load(self, *, server: str, profile: str) -> ConnectorCredential | None:
        if (
            self.credential is not None
            and self.credential.server == server
            and self.credential.profile == profile
        ):
            return self.credential
        return None

    def save(self, credential: ConnectorCredential) -> None:
        self.credential = credential

    def delete(self, *, server: str, profile: str) -> None:
        if (
            self.credential
            and self.credential.server == server
            and self.credential.profile == profile
        ):
            self.credential = None


def connector_state(*, health_status: str = "healthy") -> dict[str, Any]:
    return {
        "connector_id": "con_runtime",
        "connector_type": "codex",
        "display_name": "Codex runtime",
        "device_name": "Mars MacBook",
        "client_version": "1.0.0",
        "status": "active",
        "health_status": health_status,
        "created_at": NOW,
        "activated_at": NOW,
        "last_seen_at": NOW,
        "last_heartbeat_at": NOW,
        "last_error_code": None,
        "credential_rotated_at": None,
        "revoked_at": None,
    }


def heartbeat_json(*, health_status: str = "healthy") -> dict[str, Any]:
    return {
        "connector": connector_state(health_status=health_status),
        "agent": {
            "id": AGENT_ID,
            "address": "pluto@agentpost.me",
            "display_name": "Pluto",
        },
        "current": True,
        "server_time": NOW,
        "recommended_interval_seconds": 30,
    }


def message_json(*, status: str) -> dict[str, Any]:
    return {
        "spec_version": "0.1",
        "message_id": "msg_runtime",
        "from": {"agent_id": SENDER_ID, "address": "alice@agentpost.me"},
        "to": [{"agent_id": AGENT_ID, "address": "pluto@agentpost.me"}],
        "type": "message",
        "subject": "外部任务",
        "content": {
            "format": "text",
            "body": "untrusted content",
            "security_label": "external_agent_content",
        },
        "attachments": [],
        "thread_id": THREAD_ID,
        "reply_to": None,
        "priority": "normal",
        "requires_ack": True,
        "metadata": {},
        "created_at": NOW,
        "accepted_at": NOW,
        "expires_at": None,
        "delivery": {
            "delivery_id": DELIVERY_ID,
            "recipient_agent_id": AGENT_ID,
            "inbox_seq": 1,
            "status": status,
            "delivery_attempts": 1,
            "delivered_at": NOW,
            "read_at": NOW if status in {"read", "acked"} else None,
            "acked_at": NOW if status == "acked" else None,
            "error": None,
        },
    }


def test_keyring_store_masks_credentials_and_cursor_file_contains_only_cursor(
    tmp_path: Path,
) -> None:
    backend = FakeKeyring()
    store = KeyringCredentialStore(backend=backend)
    credential = ConnectorCredential(
        server="https://agentpost.me",
        profile="codex:mars",
        connector_id="con_runtime",
        agent_address="pluto@agentpost.me",
        api_key="agt_secret-connector-key",
    )
    store.save(credential)
    loaded = store.load(server=credential.server, profile=credential.profile)
    assert loaded == credential
    assert credential.api_key not in repr(credential)
    assert all(credential.api_key not in account for _, account in backend.values)

    cursor_path = tmp_path / "state" / "cursor.json"
    cursor_store = JsonCursorStore(cursor_path)
    cursor_store.save("opaque-cursor-token")
    assert cursor_store.load() == "opaque-cursor-token"
    assert json.loads(cursor_path.read_text()) == {"cursor": "opaque-cursor-token"}
    assert "agt_" not in cursor_path.read_text()
    assert stat.S_IMODE(cursor_path.stat().st_mode) == 0o600

    store.delete(server=credential.server, profile=credential.profile)
    assert store.load(server=credential.server, profile=credential.profile) is None


def test_keyring_store_fails_closed_with_a_machine_readable_secure_storage_code() -> None:
    store = KeyringCredentialStore(backend=UnavailableKeyring())

    with pytest.raises(Exception) as unavailable:
        store.load(server="https://agentpost.me", profile="openclaw:cloud")

    assert getattr(unavailable.value, "code", None) == "secure_credential_storage_unavailable"
    assert "secret backend detail" not in str(unavailable.value)


def test_managed_connector_restores_key_rotates_and_persists_replacement() -> None:
    requests: list[httpx.Request] = []
    store = MemoryCredentialStore(
        ConnectorCredential(
            server="https://agentpost.me",
            profile="daily-research",
            connector_id="con_runtime",
            agent_address="pluto@agentpost.me",
            api_key="agt_stored-key",
        )
    )

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/v1/connect/heartbeat":
            return httpx.Response(200, json=heartbeat_json())
        if request.url.path == "/api/v1/connect/credentials/rotate":
            assert request.headers["Authorization"] == "Bearer agt_stored-key"
            return httpx.Response(
                200,
                json={
                    "connector_id": "con_runtime",
                    "agent": heartbeat_json()["agent"],
                    "api_key": "agt_rotated-key",
                    "rotated_at": NOW,
                },
            )
        if request.url.path == "/api/v1/inbox":
            assert request.headers["Authorization"] == "Bearer agt_rotated-key"
            return httpx.Response(
                200,
                json={"items": [], "next_cursor": None, "has_more": False},
            )
        raise AssertionError(request.url)

    managed = AgentPost.connect_managed(
        "https://agentpost.me",
        connector_type="codex",
        display_name="Codex runtime",
        profile="daily-research",
        credential_store=store,
        open_browser=False,
        transport=httpx.MockTransport(handler),
    )
    try:
        assert [request.url.path for request in requests] == ["/api/v1/connect/heartbeat"]
        rotation = managed.rotate_credential()
        assert "agt_rotated-key" not in repr(rotation)
        assert store.credential is not None
        assert store.credential.api_key == "agt_rotated-key"
        assert managed.client.inbox.unread().items == []
    finally:
        managed.close()


def test_worker_advances_cursor_only_after_explicit_read_handler_and_ack() -> None:
    paths: list[str] = []
    handled: list[str] = []
    credential_store = MemoryCredentialStore(
        ConnectorCredential(
            server="https://agentpost.me",
            profile="worker",
            connector_id="con_runtime",
            agent_address="pluto@agentpost.me",
            api_key="agt_worker-key",
        )
    )

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/api/v1/connect/heartbeat":
            return httpx.Response(200, json=heartbeat_json())
        if request.url.path == "/api/v1/inbox":
            assert request.url.params.get("limit") == "1"
            return httpx.Response(
                200,
                json={
                    "items": [message_json(status="delivered")],
                    "next_cursor": "cursor-after-msg",
                    "has_more": False,
                },
            )
        if request.url.path == "/api/v1/messages/msg_runtime/read":
            return httpx.Response(200, json=message_json(status="read"))
        if request.url.path == "/api/v1/messages/msg_runtime/ack":
            return httpx.Response(200, json=message_json(status="acked"))
        raise AssertionError(request.url)

    managed = AgentPost.connect_managed(
        "https://agentpost.me",
        connector_type="codex",
        display_name="Worker",
        profile="worker",
        credential_store=credential_store,
        open_browser=False,
        transport=httpx.MockTransport(handler),
    )
    cursor_store = MemoryCursorStore()
    worker = ConnectorWorker(
        managed,
        handler=lambda message: handled.append(message.message_id),
        cursor_store=cursor_store,
    )
    try:
        assert worker.run_once() == 1
    finally:
        managed.close()
    assert handled == ["msg_runtime"]
    assert cursor_store.cursor == "cursor-after-msg"
    assert paths == [
        "/api/v1/connect/heartbeat",
        "/api/v1/connect/heartbeat",
        "/api/v1/inbox",
        "/api/v1/messages/msg_runtime/read",
        "/api/v1/messages/msg_runtime/ack",
        "/api/v1/connect/heartbeat",
    ]


def test_worker_handler_failure_keeps_cursor_for_at_least_once_replay() -> None:
    health_reports: list[str] = []
    credential_store = MemoryCredentialStore(
        ConnectorCredential(
            server="https://agentpost.me",
            profile="failing-worker",
            connector_id="con_runtime",
            agent_address="pluto@agentpost.me",
            api_key="agt_worker-key",
        )
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/connect/heartbeat":
            payload = json.loads(request.content)
            health_reports.append(payload["health_status"])
            return httpx.Response(200, json=heartbeat_json(health_status=payload["health_status"]))
        if request.url.path == "/api/v1/inbox":
            return httpx.Response(
                200,
                json={
                    "items": [message_json(status="delivered")],
                    "next_cursor": "must-not-advance",
                    "has_more": False,
                },
            )
        if request.url.path == "/api/v1/messages/msg_runtime/read":
            return httpx.Response(200, json=message_json(status="read"))
        raise AssertionError(request.url)

    managed = AgentPost.connect_managed(
        "https://agentpost.me",
        connector_type="codex",
        display_name="Worker",
        profile="failing-worker",
        credential_store=credential_store,
        open_browser=False,
        transport=httpx.MockTransport(handler),
    )
    cursor_store = MemoryCursorStore()
    worker = ConnectorWorker(
        managed,
        handler=lambda _message: (_ for _ in ()).throw(RuntimeError("handler failed")),
        cursor_store=cursor_store,
    )
    try:
        with pytest.raises(RuntimeError, match="handler failed"):
            worker.run_once()
    finally:
        managed.close()
    assert cursor_store.cursor is None
    assert health_reports == ["healthy", "healthy", "degraded"]
