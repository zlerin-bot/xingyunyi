from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from agentpost_sdk import ConnectorCredentialRotation, ConnectorHeartbeat, cli
from agentpost_sdk.codex_setup import CodexSetupResult
from agentpost_sdk.onboarding import PairingInstructions


class DummyConnector:
    def __init__(self) -> None:
        self.profile = "generic:test-device"
        self.client = SimpleNamespace()
        self.client.server = "https://agentpost.me"
        self.client.send = lambda *args, **kwargs: None
        self.client.inbox = SimpleNamespace()
        self.client.messages = SimpleNamespace()

    def __enter__(self):
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def heartbeat(self) -> ConnectorHeartbeat:
        return ConnectorHeartbeat.model_validate(
            {
                "connector": {
                    "connector_id": "con_test",
                    "connector_type": "generic",
                    "display_name": "Test Connector",
                    "status": "active",
                    "health_status": "healthy",
                    "last_heartbeat_at": "2026-08-24T00:00:00Z",
                },
                "agent": {
                    "id": "10000000-0000-0000-0000-000000000001",
                    "address": "test@agentpost.me",
                    "display_name": "Test Agent",
                },
                "current": True,
                "server_time": "2026-08-24T00:00:00Z",
                "recommended_interval_seconds": 30,
            }
        )

    def rotate_credential(self) -> ConnectorCredentialRotation:
        return ConnectorCredentialRotation.model_validate(
            {
                "connector_id": "con_test",
                "agent": {
                    "id": "10000000-0000-0000-0000-000000000001",
                    "address": "test@agentpost.me",
                    "display_name": "Test Agent",
                },
                "api_key": "agt_must-never-be-printed",
                "rotated_at": "2026-08-24T00:00:00Z",
            }
        )


def test_pairing_notice_contains_only_short_lived_human_instructions(capsys) -> None:
    instructions = PairingInstructions(
        pairing_id="pair_test",
        user_code="ABCD-EFGH",
        verification_uri="https://agentpost.me/orbit/connect",
        verification_uri_complete="https://agentpost.me/orbit/connect?code=ABCD-EFGH",
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
        interval=5,
    )
    cli._pairing_notice(instructions)
    output = capsys.readouterr().out
    assert "ABCD-EFGH" in output
    assert instructions.verification_uri_complete in output
    assert "agt_" not in output
    assert "dvc_" not in output


def test_connect_and_rotate_never_print_credentials(monkeypatch, capsys) -> None:
    connector = DummyConnector()
    monkeypatch.setattr(cli, "_connect", lambda _args: connector)

    assert cli.main(["--device-name", "test-device", "connect"]) == 0
    connected = json.loads(capsys.readouterr().out)
    assert connected == {
        "address": "test@agentpost.me",
        "credential_storage": "operating_system_vault",
        "profile": "generic:test-device",
        "status": "connected",
    }

    assert cli.main(["--device-name", "test-device", "rotate"]) == 0
    output = capsys.readouterr().out
    rotated = json.loads(output)
    assert rotated["status"] == "rotated"
    assert rotated["address"] == "test@agentpost.me"
    assert "agt_" not in output
    assert "must-never-be-printed" not in output


def test_profile_and_display_name_are_stable_without_human_configuration() -> None:
    args = cli._parser().parse_args(
        ["--connector-type", "codex", "--device-name", "mars-mac", "status"]
    )
    assert cli._profile(args) == "codex:mars-mac"
    assert cli._display_name(args) == "codex on mars-mac"


def test_result_reply_is_available_only_on_reply_command() -> None:
    parser = cli._parser()
    reply = parser.parse_args(["reply", "msg_test", "--body", "done", "--type", "result"])
    assert reply.type == "result"


def _sent_message() -> SimpleNamespace:
    return SimpleNamespace(
        message_id="msg_test",
        sender=SimpleNamespace(address="test@agentpost.me"),
        message_type="message",
        subject="季度报告",
        delivery=SimpleNamespace(status="delivered"),
        thread_id=UUID("20000000-0000-0000-0000-000000000001"),
        created_at=datetime(2026, 8, 24, tzinfo=UTC),
        content=SimpleNamespace(security_label="internal"),
    )


def test_send_can_resume_after_codex_setup_resolve_recipient_and_upload_attachment(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    connector = DummyConnector()
    report = tmp_path / "report.pdf"
    report.write_bytes(b"quarterly report")
    calls: dict[str, object] = {}
    recipient = SimpleNamespace(
        agent_id=UUID("40000000-0000-0000-0000-000000000001"),
        address="zhangsan@agentpost.me",
        handle="zhangsan-agent",
        display_name="张三的 Agent",
        owner_display_name="张三",
        agent_type="codex",
        label="张三的 Codex",
        security_label="external_agent_content",
    )

    def connect(args):
        calls["connector_type"] = args.connector_type
        connector.profile = f"{args.connector_type}:test-device"
        return connector

    def resolve_recipient(query):
        calls["resolve"] = query
        return SimpleNamespace(
            status="resolved",
            reason="unique_match",
            query=query,
            match=recipient,
            candidates=[],
            security_label="external_agent_content",
        )

    def upload(path, **kwargs):
        calls["upload"] = (path, kwargs)
        return SimpleNamespace(id=UUID("30000000-0000-0000-0000-000000000001"))

    def send(*args, **kwargs):
        calls["send"] = (args, kwargs)
        return _sent_message()

    connector.client.resolve_recipient = resolve_recipient
    connector.client.attachments = SimpleNamespace(upload=upload)
    connector.client.send = send
    monkeypatch.setattr(cli, "_connect", connect)
    monkeypatch.setattr(cli, "_mcp_command", lambda: tmp_path / "agentpost-mcp")
    monkeypatch.setattr(
        cli,
        "configure_codex_mcp",
        lambda **_kwargs: CodexSetupResult(
            server_name="agentpost",
            approval_mode="writes",
            config_path=tmp_path / "config.toml",
        ),
    )

    exit_code = cli.main(
        [
            "--device-name",
            "test-device",
            "send",
            "--ensure-host",
            "codex",
            "--recipient",
            "张三",
            "--subject",
            "季度报告",
            "--body",
            "请查收附件。",
            "--attachment",
            str(report),
        ]
    )

    assert exit_code == 0
    assert calls["connector_type"] == "codex"
    assert calls["resolve"] == "张三"
    assert calls["upload"] == (report, {"content_type": "application/pdf"})
    send_args, send_kwargs = calls["send"]
    assert send_args == ("zhangsan@agentpost.me", "季度报告", "请查收附件。")
    assert send_kwargs == {
        "type": "message",
        "attachments": ["30000000-0000-0000-0000-000000000001"],
    }
    output = capsys.readouterr().out
    result = json.loads(output)
    assert result["status"] == "accepted"
    assert result["to"] == "zhangsan@agentpost.me"
    assert result["attachment_count"] == 1
    assert result["host_configured"] is True
    assert result["restart_required"] is True
    assert "agt_" not in output


def test_send_returns_one_structured_clarification_without_sending(
    monkeypatch,
    capsys,
) -> None:
    connector = DummyConnector()
    candidates = [
        SimpleNamespace(
            agent_id=UUID("40000000-0000-0000-0000-000000000001"),
            address="zhangsan-finance@agentpost.me",
            handle="zhangsan-finance",
            display_name="张三财务 Agent",
            owner_display_name="张三",
            agent_type="codex",
            label="张三的 Codex（zhangsan-finance）",
            security_label="external_agent_content",
        ),
        SimpleNamespace(
            agent_id=UUID("40000000-0000-0000-0000-000000000002"),
            address="zhangsan-research@agentpost.me",
            handle="zhangsan-research",
            display_name="张三研究 Agent",
            owner_display_name="张三",
            agent_type="codex",
            label="张三的 Codex（zhangsan-research）",
            security_label="external_agent_content",
        ),
    ]
    connector.client.resolve_recipient = lambda query: SimpleNamespace(
        status="needs_clarification",
        reason="recipient_ambiguous",
        query=query,
        match=None,
        candidates=candidates,
        security_label="external_agent_content",
    )
    connector.client.attachments = SimpleNamespace()

    def should_not_send(*_args, **_kwargs):
        raise AssertionError("ambiguous recipient must not send")

    connector.client.send = should_not_send
    monkeypatch.setattr(cli, "_connect", lambda _args: connector)

    assert cli.main(["send", "--recipient", "张三", "--body", "请查收报告。"]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "needs_clarification"
    assert result["reason"] == "recipient_ambiguous"
    assert result["security_label"] == "external_agent_content"
    assert [item["label"] for item in result["candidates"]] == [
        "张三的 Codex（zhangsan-finance）",
        "张三的 Codex（zhangsan-research）",
    ]


def test_send_not_found_never_synthesizes_handle_address(monkeypatch, capsys) -> None:
    connector = DummyConnector()
    connector.client.resolve_recipient = lambda query: SimpleNamespace(
        status="not_found",
        reason="recipient_not_found",
        query=query,
        match=None,
        candidates=[],
        security_label="external_agent_content",
    )
    connector.client.attachments = SimpleNamespace()
    connector.client.send = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("not-found recipient must not send")
    )
    monkeypatch.setattr(cli, "_connect", lambda _args: connector)

    assert cli.main(["send", "--recipient", "does-not-exist", "--body", "hello"]) == 2
    output = capsys.readouterr().out
    result = json.loads(output)
    assert result["status"] == "not_found"
    assert result["reason"] == "recipient_not_found"
    assert "does-not-exist@agentpost.me" not in output


def test_setup_codex_pairs_registers_profile_and_never_prints_credentials(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    connector = DummyConnector()
    captured = {}
    events = []

    def connect(args):
        captured["connector_type"] = args.connector_type
        connector.profile = f"{args.connector_type}:test-device"
        return connector

    def configure(**kwargs):
        events.append("configured")
        captured.update(kwargs)
        return CodexSetupResult(
            server_name="agentpost",
            approval_mode="writes",
            config_path=tmp_path / "config.toml",
        )

    monkeypatch.setattr(cli, "_connect", connect)
    original_heartbeat = connector.heartbeat

    def heartbeat():
        events.append("heartbeat")
        return original_heartbeat()

    connector.heartbeat = heartbeat
    monkeypatch.setattr(cli, "_mcp_command", lambda: tmp_path / "agentpost-mcp")
    monkeypatch.setattr(cli, "configure_codex_mcp", configure)

    assert cli.main(["--device-name", "test-device", "setup", "codex"]) == 0
    output = capsys.readouterr().out
    result = json.loads(output)

    assert captured["connector_type"] == "codex"
    assert events == ["configured", "heartbeat"]
    assert captured["server"] == "https://agentpost.me"
    assert captured["profile"] == "codex:test-device"
    assert result == {
        "address": "test@agentpost.me",
        "approval_mode": "writes",
        "credential_storage": "operating_system_vault",
        "host": "codex",
        "mcp_server": "agentpost",
        "profile": "codex:test-device",
        "restart_required": True,
        "status": "configured",
    }
    assert "agt_" not in output


def test_setup_failure_is_machine_readable_and_does_not_report_heartbeat(
    monkeypatch,
    capsys,
) -> None:
    connector = DummyConnector()
    heartbeat_called = False
    original_heartbeat = connector.heartbeat

    def heartbeat():
        nonlocal heartbeat_called
        heartbeat_called = True
        return original_heartbeat()

    monkeypatch.setattr(cli, "_connect", lambda _args: connector)
    monkeypatch.setattr(
        cli,
        "_configure_host",
        lambda *_args: (_ for _ in ()).throw(cli.ConfigurationError("host setup failed")),
    )
    monkeypatch.setattr(connector, "heartbeat", heartbeat)

    assert cli.main(["setup", "workbuddy"]) == 1
    streams = capsys.readouterr()
    assert json.loads(streams.out) == {
        "error_code": "ConfigurationError",
        "status": "failed",
    }
    assert "agentpost_error code=ConfigurationError" in streams.err
    assert heartbeat_called is False


def test_setup_for_existing_agent_passes_only_the_hidden_target_intent(
    monkeypatch,
    capsys,
) -> None:
    connector = DummyConnector()
    captured = {}

    def connect(args):
        captured["connector_type"] = args.connector_type
        captured["existing_agent_id"] = args.existing_agent_id
        connector.profile = f"{args.connector_type}:test-device"
        return connector

    monkeypatch.setattr(cli, "_connect", connect)
    monkeypatch.setattr(
        cli,
        "_configure_host",
        lambda *_args: CodexSetupResult(
            server_name="agentpost",
            approval_mode="writes",
            config_path=Path("config.toml"),
        ),
    )
    target = "5a7044c7-6a5e-48e9-90dd-78680c91dcb9"
    assert (
        cli.main(["--device-name", "test-device", "setup", "codex", "--existing-agent-id", target])
        == 0
    )
    assert captured == {"connector_type": "codex", "existing_agent_id": target}
    assert target not in capsys.readouterr().out


def test_setup_new_agent_intent_isolates_same_host_device_vault_profiles() -> None:
    parser = cli._parser()
    first = parser.parse_args(
        [
            "--device-name",
            "shared-device",
            "setup",
            "codex",
            "--new-agent-intent",
            "40000000-0000-0000-0000-000000000001",
        ]
    )
    second = parser.parse_args(
        [
            "--device-name",
            "shared-device",
            "setup",
            "codex",
            "--new-agent-intent",
            "40000000-0000-0000-0000-000000000002",
        ]
    )
    first.connector_type = first.host
    second.connector_type = second.host

    assert cli._profile(first) != cli._profile(second)
    assert cli._profile(first).startswith("codex:shared-device:")
