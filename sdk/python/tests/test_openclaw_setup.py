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
    preflight_openclaw_mcp,
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
        stdout = _successful_probe() if command[-2:] == ["agentpost", "--json"] else ""
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
    assert calls[:2] == [
        ("/opt/openclaw", "mcp", "set", "--help"),
        ("/opt/openclaw", "mcp", "probe", "--help"),
    ]
    assert calls[2][:4] == ("/opt/openclaw", "mcp", "set", "agentpost")
    assert calls[3] == ("/opt/openclaw", "mcp", "probe", "agentpost", "--json")
    definition = json.loads(calls[2][4])
    assert definition == {
        "command": str(_executable(tmp_path).resolve()),
        "args": [],
        "env": {
            "AGENTPOST_SERVER": "https://agentpost.me",
            "AGENTPOST_PROFILE": "openclaw:test-device",
        },
    }
    assert "AGENTPOST_API_KEY" not in calls[2][4]
    assert "agt_" not in calls[2][4]


def test_configure_openclaw_passes_only_non_secret_session_collection_hint(
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, ...]] = []

    def runner(command, **_kwargs):
        calls.append(tuple(command))
        stdout = _successful_probe() if command[-2:] == ["agentpost", "--json"] else ""
        return SimpleNamespace(returncode=0, stdout=stdout)

    configure_openclaw_mcp(
        server="https://agentpost.me",
        profile="openclaw:headless-linux",
        mcp_command=_executable(tmp_path),
        openclaw_command="/opt/openclaw",
        keyring_collection="session",
        runner=runner,
    )

    definition = json.loads(calls[2][4])
    assert definition["env"] == {
        "AGENTPOST_SERVER": "https://agentpost.me",
        "AGENTPOST_PROFILE": "openclaw:headless-linux",
        "AGENTPOST_KEYRING_COLLECTION": "session",
    }
    assert "agt_" not in calls[2][4]


def test_configure_openclaw_rejects_unknown_keyring_collection(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="unsupported AgentPost keyring collection"):
        configure_openclaw_mcp(
            server="https://agentpost.me",
            profile="openclaw:headless-linux",
            mcp_command=_executable(tmp_path),
            openclaw_command="/opt/openclaw",
            keyring_collection="plaintext-file",
        )


def test_configure_openclaw_sanitizes_cli_failure(tmp_path: Path) -> None:
    calls = 0

    def runner(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return SimpleNamespace(returncode=1 if calls == 3 else 0, stdout="secret")

    with pytest.raises(ConfigurationError, match="OpenClaw MCP registration failed"):
        configure_openclaw_mcp(
            server="https://agentpost.me",
            profile="openclaw:test-device",
            mcp_command=_executable(tmp_path),
            openclaw_command="/opt/openclaw",
            runner=runner,
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
        return SimpleNamespace(returncode=0, stdout=probe_stdout if calls == 4 else "")

    with pytest.raises(ConfigurationError, match=message):
        configure_openclaw_mcp(
            server="https://agentpost.me",
            profile="openclaw:test-device",
            mcp_command=_executable(tmp_path),
            openclaw_command="/opt/openclaw",
            runner=runner,
        )


def test_openclaw_preflight_reports_actionable_host_codes() -> None:
    with pytest.raises(ConfigurationError) as missing:
        preflight_openclaw_mcp(openclaw_command="", runner=lambda *_args, **_kwargs: None)
    assert missing.value.code == "openclaw_not_available"

    with pytest.raises(ConfigurationError) as outdated:
        preflight_openclaw_mcp(
            openclaw_command="/opt/openclaw",
            runner=lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout="secret"),
        )
    assert outdated.value.code == "openclaw_mcp_upgrade_required"


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
