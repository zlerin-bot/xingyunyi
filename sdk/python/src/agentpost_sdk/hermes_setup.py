"""Hermes MCP registration without exposing the paired Agent credential."""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from agentpost_sdk.errors import ConfigurationError

MCP_SERVER_NAME = "agentpost"


class CommandResult(Protocol):
    returncode: int
    stdout: str


CommandRunner = Callable[..., CommandResult]


@dataclass(frozen=True, slots=True)
class HermesSetupResult:
    server_name: str
    approval_mode: str
    config_path: Path
    restart_required: bool = False


def _config_path() -> Path:
    explicit_home = os.environ.get("HERMES_HOME", "").strip()
    if explicit_home:
        return Path(explicit_home).expanduser() / "config.yaml"
    return Path.home() / ".hermes" / "config.yaml"


def _run_hermes(
    runner: CommandRunner,
    command: list[str],
) -> CommandResult:
    try:
        return runner(
            command,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ConfigurationError("Hermes MCP registration could not be started") from exc


def preflight_hermes_mcp(
    *,
    hermes_command: str | None = None,
    runner: CommandRunner = subprocess.run,
) -> str:
    """Verify Hermes's supported MCP CLI before Human pairing starts."""

    resolved_hermes = hermes_command or shutil.which("hermes")
    if not resolved_hermes:
        raise ConfigurationError(
            "Hermes is not installed or not available on PATH",
            code="hermes_not_available",
        )
    checks = (
        [resolved_hermes, "config", "set", "--help"],
        [resolved_hermes, "mcp", "test", "--help"],
    )
    for command in checks:
        completed = _run_hermes(runner, command)
        if completed.returncode != 0:
            raise ConfigurationError(
                "Hermes must be updated to a release with config set and MCP test support",
                code="hermes_mcp_upgrade_required",
            )
    return resolved_hermes


def configure_hermes_mcp(
    *,
    server: str,
    profile: str,
    mcp_command: Path,
    hermes_command: str | None = None,
    keyring_collection: str | None = None,
    runner: CommandRunner = subprocess.run,
) -> HermesSetupResult:
    """Idempotently add AgentPost through Hermes's validated MCP CLI."""

    cleaned_server = server.strip().rstrip("/")
    cleaned_profile = profile.strip()
    if not cleaned_server:
        raise ConfigurationError("AgentPost server must not be empty")
    if not cleaned_profile or len(cleaned_profile) > 200:
        raise ConfigurationError("Connector profile must contain 1-200 characters")
    if keyring_collection not in {None, "session"}:
        raise ConfigurationError("unsupported AgentPost keyring collection")
    executable = mcp_command.expanduser().resolve()
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise ConfigurationError("agentpost-mcp is not installed in this runtime")
    resolved_hermes = preflight_hermes_mcp(
        hermes_command=hermes_command,
        runner=runner,
    )

    config_values = {
        f"mcp_servers.{MCP_SERVER_NAME}.command": str(executable),
        f"mcp_servers.{MCP_SERVER_NAME}.env.AGENTPOST_SERVER": cleaned_server,
        f"mcp_servers.{MCP_SERVER_NAME}.env.AGENTPOST_PROFILE": cleaned_profile,
        f"mcp_servers.{MCP_SERVER_NAME}.env.AGENTPOST_KEYRING_COLLECTION": (
            keyring_collection or ""
        ),
    }
    for key, value in config_values.items():
        configured = _run_hermes(
            runner,
            [resolved_hermes, "config", "set", "--force", key, value],
        )
        if configured.returncode != 0:
            raise ConfigurationError("Hermes MCP registration failed")

    tested = _run_hermes(
        runner,
        [resolved_hermes, "mcp", "test", MCP_SERVER_NAME],
    )
    if tested.returncode != 0:
        raise ConfigurationError("Hermes could not load the AgentPost MCP tools")

    return HermesSetupResult(
        server_name=MCP_SERVER_NAME,
        approval_mode="host",
        config_path=_config_path(),
    )
