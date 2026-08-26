from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from agentpost_sdk.errors import ConfigurationError
from agentpost_sdk.hermes_setup import configure_hermes_mcp, preflight_hermes_mcp


def _executable(path: Path) -> Path:
    path.write_text("", encoding="utf-8")
    path.chmod(0o700)
    return path


def test_configure_hermes_uses_official_cli_and_only_non_secret_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))
    mcp = _executable(tmp_path / "agentpost-mcp")
    calls: list[tuple[list[str], dict[str, object]]] = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="ok")

    result = configure_hermes_mcp(
        server="https://agentpost.me/",
        profile="hermes:test-device",
        mcp_command=mcp,
        hermes_command="/opt/hermes/bin/hermes",
        keyring_collection="session",
        runner=runner,
    )

    assert [call[0][1:3] for call in calls] == [
        ["config", "set"],
        ["mcp", "test"],
        ["config", "set"],
        ["config", "set"],
        ["config", "set"],
        ["config", "set"],
        ["mcp", "test"],
    ]
    assert calls[2][0] == [
        "/opt/hermes/bin/hermes",
        "config",
        "set",
        "--force",
        "mcp_servers.agentpost.command",
        str(mcp),
    ]
    assert calls[3][0][-2:] == [
        "mcp_servers.agentpost.env.AGENTPOST_SERVER",
        "https://agentpost.me",
    ]
    assert calls[4][0][-2:] == [
        "mcp_servers.agentpost.env.AGENTPOST_PROFILE",
        "hermes:test-device",
    ]
    assert calls[5][0][-2:] == [
        "mcp_servers.agentpost.env.AGENTPOST_KEYRING_COLLECTION",
        "session",
    ]
    assert calls[6][0] == ["/opt/hermes/bin/hermes", "mcp", "test", "agentpost"]
    assert result.server_name == "agentpost"
    assert result.config_path == tmp_path / "hermes-home" / "config.yaml"
    assert result.restart_required is False
    assert "agt_" not in str(calls)


def test_preflight_hermes_requires_add_and_test_support() -> None:
    def runner(command, **_kwargs):
        return SimpleNamespace(
            returncode=1 if command[1:3] == ["mcp", "test"] else 0,
            stdout="",
        )

    with pytest.raises(ConfigurationError) as raised:
        preflight_hermes_mcp(hermes_command="hermes", runner=runner)

    assert raised.value.code == "hermes_mcp_upgrade_required"


def test_configure_hermes_rejects_invalid_storage_or_unexecutable_mcp(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "agentpost-mcp"
    executable.write_text("", encoding="utf-8")
    executable.chmod(0o600)

    with pytest.raises(ConfigurationError, match="unsupported AgentPost keyring"):
        configure_hermes_mcp(
            server="https://agentpost.me",
            profile="hermes:test",
            mcp_command=executable,
            keyring_collection="login",
        )
    with pytest.raises(ConfigurationError, match="not installed"):
        configure_hermes_mcp(
            server="https://agentpost.me",
            profile="hermes:test",
            mcp_command=executable,
        )


def test_configure_hermes_fails_when_registration_or_probe_fails(
    tmp_path: Path,
) -> None:
    executable = _executable(tmp_path / "agentpost-mcp")

    def config_fails(command, **_kwargs):
        is_config_execution = command[1:3] == ["config", "set"] and "--help" not in command
        return SimpleNamespace(returncode=1 if is_config_execution else 0, stdout="")

    with pytest.raises(ConfigurationError, match="registration failed"):
        configure_hermes_mcp(
            server="https://agentpost.me",
            profile="hermes:test",
            mcp_command=executable,
            hermes_command="hermes",
            runner=config_fails,
        )

    def probe_fails(command, **_kwargs):
        is_test_execution = command[1:3] == ["mcp", "test"] and "--help" not in command
        return SimpleNamespace(returncode=1 if is_test_execution else 0, stdout="")

    with pytest.raises(ConfigurationError, match="could not load"):
        configure_hermes_mcp(
            server="https://agentpost.me",
            profile="hermes:test",
            mcp_command=executable,
            hermes_command="hermes",
            runner=probe_fails,
        )
