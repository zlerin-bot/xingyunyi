from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from agentpost_sdk.errors import ConfigurationError
from agentpost_sdk.openclaw_setup import (
    EXPECTED_MCP_TOOLS,
    _config_path,
    configure_openclaw_mcp,
)


def _executable(tmp_path: Path) -> Path:
    command = tmp_path / "agentpost-mcp"
    command.write_text("#!/bin/sh\n", encoding="utf-8")
    command.chmod(0o700)
    return command


def _successful_probe() -> str:
    return json.dumps(
        {
            "servers": {"agentpost": {"tools": len(EXPECTED_MCP_TOOLS)}},
            "tools": [f"agentpost__{name}" for name in sorted(EXPECTED_MCP_TOOLS)],
            "diagnostics": [],
        }
    )


def test_configure_openclaw_uses_validated_cli_and_profile_reference(
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, ...]] = []

    def runner(command, **_kwargs):
        calls.append(tuple(command))
        stdout = _successful_probe() if command[1:3] == ["mcp", "probe"] else ""
        return SimpleNamespace(returncode=0, stdout=stdout)

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
    assert calls[1] == ("/opt/openclaw", "mcp", "probe", "agentpost", "--json")
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


@pytest.mark.parametrize(
    ("probe_stdout", "message"),
    [
        (
            json.dumps(
                {
                    "servers": {},
                    "tools": [],
                    "diagnostics": [{"message": "secret process detail"}],
                }
            ),
            "OpenClaw could not load the AgentPost MCP tools",
        ),
        ("not-json", "OpenClaw MCP verification returned malformed output"),
    ],
)
def test_configure_openclaw_requires_a_successful_live_probe(
    tmp_path: Path,
    probe_stdout: str,
    message: str,
) -> None:
    calls = 0

    def runner(_command, **_kwargs):
        nonlocal calls
        calls += 1
        return SimpleNamespace(returncode=0, stdout=probe_stdout if calls == 2 else "")

    with pytest.raises(ConfigurationError, match=message):
        configure_openclaw_mcp(
            server="https://agentpost.me",
            profile="openclaw:test-device",
            mcp_command=_executable(tmp_path),
            openclaw_command="/opt/openclaw",
            runner=runner,
        )


def test_configure_openclaw_reports_official_config_path_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    state = tmp_path / "state"
    explicit = tmp_path / "custom" / "openclaw.json"
    monkeypatch.setenv("OPENCLAW_HOME", str(home))
    assert _config_path() == home / ".openclaw" / "openclaw.json"

    monkeypatch.setenv("OPENCLAW_STATE_DIR", str(state))
    assert _config_path() == state / "openclaw.json"

    monkeypatch.setenv("OPENCLAW_CONFIG_PATH", str(explicit))
    assert _config_path() == explicit
