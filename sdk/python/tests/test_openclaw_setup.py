from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from agentpost_sdk.errors import ConfigurationError
from agentpost_sdk.openclaw_setup import configure_openclaw_mcp


def _executable(tmp_path: Path) -> Path:
    command = tmp_path / "agentpost-mcp"
    command.write_text("#!/bin/sh\n", encoding="utf-8")
    command.chmod(0o700)
    return command


def test_configure_openclaw_uses_validated_cli_and_profile_reference(tmp_path: Path) -> None:
    calls: list[tuple[str, ...]] = []

    def runner(command, **_kwargs):
        calls.append(tuple(command))
        return SimpleNamespace(returncode=0, stdout="")

    result = configure_openclaw_mcp(
        server="https://agentpost.me/",
        profile="openclaw:test-device",
        mcp_command=_executable(tmp_path),
        openclaw_command="/opt/openclaw",
        runner=runner,
    )

    assert result.approval_mode == "host"
    assert result.restart_required is False
    assert calls[0][:4] == ("/opt/openclaw", "mcp", "set", "agentpost")
    definition = json.loads(calls[0][4])
    assert definition == {
        "command": str(_executable(tmp_path).resolve()),
        "args": [],
        "env": {
            "AGENTPOST_SERVER": "https://agentpost.me",
            "AGENTPOST_PROFILE": "openclaw:test-device",
        },
    }
    assert "AGENTPOST_API_KEY" not in calls[0][4]
    assert "agt_" not in calls[0][4]


def test_configure_openclaw_sanitizes_cli_failure(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="OpenClaw MCP registration failed"):
        configure_openclaw_mcp(
            server="https://agentpost.me",
            profile="openclaw:test-device",
            mcp_command=_executable(tmp_path),
            openclaw_command="/opt/openclaw",
            runner=lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout="secret"),
        )
