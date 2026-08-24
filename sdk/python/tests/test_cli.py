from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from agentpost_sdk import ConnectorCredentialRotation, ConnectorHeartbeat, cli
from agentpost_sdk.onboarding import PairingInstructions


class DummyConnector:
    def __init__(self) -> None:
        self.profile = "generic:test-device"
        self.client = SimpleNamespace()
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
