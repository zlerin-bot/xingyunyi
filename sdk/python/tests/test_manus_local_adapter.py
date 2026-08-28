from __future__ import annotations

import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from agentpost_sdk.connector import ConnectorCredential
from agentpost_sdk.manus_local_adapter import ManusLocalAdapterError, run
from agentpost_sdk.manus_setup import configure_manus_local_folder


class FakeMessage:
    def model_dump(self, **_kwargs):
        return {"message_id": "msg_test", "delivery": {"status": "accepted"}}


class FakeChannel:
    def model_dump(self, **_kwargs):
        return {"organization_id": "11111111-1111-4111-8111-111111111111", "agents": []}


class FakeStore:
    def __init__(self, credential: ConnectorCredential | None) -> None:
        self.credential = credential

    def load(self, *, server: str, profile: str):
        assert server == "https://agentpost.me"
        assert profile == "manus:test-device"
        return self.credential


class FakeClient:
    instances: list[FakeClient] = []

    def __init__(self, server: str, api_key: str) -> None:
        assert server == "https://agentpost.me"
        assert api_key == "vault-secret"
        self.sent: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self.organization_sent: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self.connector = SimpleNamespace(heartbeat=self._heartbeat)
        self.inbox = SimpleNamespace()
        self.messages = SimpleNamespace()
        self.__class__.instances.append(self)

    def _heartbeat(self):
        return SimpleNamespace(
            current=True,
            agent=SimpleNamespace(address="020-manus-001@agentpost.me"),
            connector=SimpleNamespace(status="active", health_status="healthy"),
        )

    def send(self, *args, **kwargs):
        self.sent.append((args, kwargs))
        return FakeMessage()

    def get_organization_channel(self):
        return FakeChannel()

    def send_organization_message(self, *args, **kwargs):
        self.organization_sent.append((args, kwargs))
        return FakeMessage()

    def close(self) -> None:
        return None


def _adapter(tmp_path: Path) -> Path:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    mcp = runtime / "agentpost-mcp"
    adapter = runtime / "agentpost-manus-folder"
    mcp.write_text("#!/bin/sh\n", encoding="utf-8")
    adapter.write_text("#!/bin/sh\n", encoding="utf-8")
    mcp.chmod(0o700)
    adapter.chmod(0o700)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return configure_manus_local_folder(
        server="https://agentpost.me",
        profile="manus:test-device",
        expected_agent_address="020-manus-001@agentpost.me",
        mcp_command=mcp,
        workspace_path=workspace,
    ).command


def _credential() -> ConnectorCredential:
    return ConnectorCredential(
        server="https://agentpost.me",
        profile="manus:test-device",
        connector_id="con_test",
        agent_address="020-manus-001@agentpost.me",
        api_key="vault-secret",
    )


def test_status_verifies_vault_identity_and_live_connector(tmp_path: Path) -> None:
    result = run(
        _adapter(tmp_path),
        ["status"],
        stdin=io.BytesIO(),
        credential_store=FakeStore(_credential()),
        client_factory=FakeClient,
    )

    assert result == {
        "status": "ok",
        "current": True,
        "agent_address": "020-manus-001@agentpost.me",
        "connector": {"status": "active", "health_status": "healthy"},
    }


def test_send_accepts_message_body_only_through_stdin(tmp_path: Path) -> None:
    FakeClient.instances.clear()
    body = "来自 Manus 本地文件夹的正文"
    request = json.dumps(
        {
            "operation": "send",
            "to": "recipient@agentpost.me",
            "subject": "测试",
            "body": body,
        }
    ).encode()

    result = run(
        _adapter(tmp_path),
        ["request-stdin"],
        stdin=io.BytesIO(request),
        credential_store=FakeStore(_credential()),
        client_factory=FakeClient,
    )

    assert result["status"] == "accepted"
    args, kwargs = FakeClient.instances[-1].sent[-1]
    assert args[:2] == ("recipient@agentpost.me", "测试")
    assert args[2] == body
    assert "api_key" not in kwargs


def test_missing_vault_profile_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ManusLocalAdapterError, match="manus_vault_profile_missing"):
        run(
            _adapter(tmp_path),
            ["status"],
            stdin=io.BytesIO(),
            credential_store=FakeStore(None),
            client_factory=FakeClient,
        )


def test_organization_channel_and_send_use_explicit_operations(tmp_path: Path) -> None:
    FakeClient.instances.clear()
    adapter = _adapter(tmp_path)
    channel_result = run(
        adapter,
        ["request-stdin"],
        stdin=io.BytesIO(json.dumps({"operation": "organization_channel"}).encode()),
        credential_store=FakeStore(_credential()),
        client_factory=FakeClient,
    )
    assert channel_result["channel"]["agents"] == []

    request = {
        "operation": "organization_send",
        "organization_id": "11111111-1111-4111-8111-111111111111",
        "subject": "群内协作",
        "body": "请 020 回复，其他 Agent 了解背景。",
        "requested_responder_agent_ids": ["22222222-2222-4222-8222-222222222222"],
    }
    result = run(
        adapter,
        ["request-stdin"],
        stdin=io.BytesIO(json.dumps(request).encode()),
        credential_store=FakeStore(_credential()),
        client_factory=FakeClient,
    )
    assert result["status"] == "accepted"
    args, kwargs = FakeClient.instances[-1].organization_sent[-1]
    assert args[:3] == (
        "11111111-1111-4111-8111-111111111111",
        "群内协作",
        "请 020 回复，其他 Agent 了解背景。",
    )
    assert kwargs["requested_responder_agent_ids"] == ["22222222-2222-4222-8222-222222222222"]
