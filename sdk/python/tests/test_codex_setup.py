from __future__ import annotations

import json
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest
from agentpost_sdk.codex_setup import configure_codex_mcp
from agentpost_sdk.errors import ConfigurationError


def _executable(tmp_path: Path) -> Path:
    command = tmp_path / "agentpost-mcp"
    command.write_text("#!/bin/sh\n", encoding="utf-8")
    command.chmod(0o700)
    return command


class FakeCodexRunner:
    def __init__(self, *, returncode: int = 0) -> None:
        self.returncode = returncode
        self.calls: list[tuple[tuple[str, ...], dict[str, str]]] = []

    def __call__(self, command, **kwargs):
        environment = kwargs["env"]
        self.calls.append((tuple(command), environment.copy()))
        if self.returncode == 0:
            home = Path(environment["CODEX_HOME"])
            assert home.is_dir()
            profile = next(
                item.removeprefix("AGENTPOST_PROFILE=")
                for item in command
                if item.startswith("AGENTPOST_PROFILE=")
            )
            server = next(
                item.removeprefix("AGENTPOST_SERVER=")
                for item in command
                if item.startswith("AGENTPOST_SERVER=")
            )
            home.joinpath("config.toml").write_text(
                "[mcp_servers.unrelated]\n"
                'command = "/opt/unrelated"\n\n'
                "[mcp_servers.agentpost]\n"
                f"command = {json.dumps(str(command[-1]))}\n\n"
                "[mcp_servers.agentpost.env]\n"
                f"AGENTPOST_PROFILE = {json.dumps(profile)}\n"
                f"AGENTPOST_SERVER = {json.dumps(server)}\n",
                encoding="utf-8",
            )
        return SimpleNamespace(returncode=self.returncode)


def test_configure_codex_mcp_is_idempotent_and_stores_only_profile_reference(
    tmp_path: Path,
) -> None:
    executable = _executable(tmp_path)
    codex_home = tmp_path / "codex-home"
    runner = FakeCodexRunner()

    first = configure_codex_mcp(
        server="https://agentpost.me/",
        profile="codex:test-device",
        mcp_command=executable,
        codex_command="/opt/codex",
        codex_home=codex_home,
        runner=runner,
    )
    second = configure_codex_mcp(
        server="https://agentpost.me",
        profile="codex:test-device",
        mcp_command=executable,
        codex_command="/opt/codex",
        codex_home=codex_home,
        runner=runner,
    )

    assert first == second
    assert codex_home.is_dir()
    assert first.approval_mode == "writes"
    assert first.restart_required is True
    assert len(runner.calls) == 2
    command, environment = runner.calls[-1]
    assert command == (
        "/opt/codex",
        "mcp",
        "add",
        "agentpost",
        "--env",
        "AGENTPOST_SERVER=https://agentpost.me",
        "--env",
        "AGENTPOST_PROFILE=codex:test-device",
        "--",
        str(executable),
    )
    assert environment["CODEX_HOME"] == str(codex_home)
    assert all("API_KEY" not in item and "agt_" not in item for item in command)

    config_text = first.config_path.read_text(encoding="utf-8")
    config = tomllib.loads(config_text)
    assert config["mcp_servers"]["unrelated"]["command"] == "/opt/unrelated"
    agentpost = config["mcp_servers"]["agentpost"]
    assert agentpost["command"] == str(executable)
    assert agentpost["default_tools_approval_mode"] == "writes"
    assert agentpost["env"] == {
        "AGENTPOST_PROFILE": "codex:test-device",
        "AGENTPOST_SERVER": "https://agentpost.me",
    }
    assert config_text.count("default_tools_approval_mode") == 1
    assert "AGENTPOST_API_KEY" not in config_text
    assert "agt_" not in config_text


def test_codex_registration_failure_is_sanitized_and_does_not_patch_config(
    tmp_path: Path,
) -> None:
    runner = FakeCodexRunner(returncode=1)
    with pytest.raises(ConfigurationError, match="Codex MCP registration failed") as error:
        configure_codex_mcp(
            server="https://agentpost.me",
            profile="codex:test-device",
            mcp_command=_executable(tmp_path),
            codex_command="/opt/codex",
            codex_home=tmp_path / "codex-home",
            runner=runner,
        )

    assert "agt_" not in str(error.value)
    assert not (tmp_path / "codex-home" / "config.toml").exists()


def test_codex_setup_rejects_missing_local_mcp_runtime(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="agentpost-mcp is not installed"):
        configure_codex_mcp(
            server="https://agentpost.me",
            profile="codex:test-device",
            mcp_command=tmp_path / "missing-agentpost-mcp",
            codex_command="/opt/codex",
            codex_home=tmp_path / "codex-home",
            runner=FakeCodexRunner(),
        )
