"""OpenClaw MCP registration without exposing the paired Agent credential."""

from __future__ import annotations

import json
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
class OpenClawSetupResult:
    server_name: str
    approval_mode: str
    config_path: Path
    restart_required: bool = False


def configure_openclaw_mcp(
    *,
    server: str,
    profile: str,
    mcp_command: Path,
    openclaw_command: str | None = None,
    runner: CommandRunner = subprocess.run,
) -> OpenClawSetupResult:
    """Idempotently add AgentPost through OpenClaw's validated MCP CLI."""

    cleaned_server = server.strip().rstrip("/")
    cleaned_profile = profile.strip()
    if not cleaned_server:
        raise ConfigurationError("AgentPost server must not be empty")
    if not cleaned_profile or len(cleaned_profile) > 200:
        raise ConfigurationError("Connector profile must contain 1-200 characters")
    executable = mcp_command.expanduser().resolve()
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise ConfigurationError("agentpost-mcp is not installed in this runtime")
    resolved_openclaw = openclaw_command or shutil.which("openclaw")
    if not resolved_openclaw:
        raise ConfigurationError("OpenClaw is not installed or not available on PATH")

    definition = {
        "command": str(executable),
        "args": [],
        "env": {
            "AGENTPOST_SERVER": cleaned_server,
            "AGENTPOST_PROFILE": cleaned_profile,
        },
    }
    command = [
        resolved_openclaw,
        "mcp",
        "set",
        MCP_SERVER_NAME,
        json.dumps(definition, ensure_ascii=False, separators=(",", ":")),
    ]
    try:
        completed = runner(
            command,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ConfigurationError("OpenClaw MCP registration could not be started") from exc
    if completed.returncode != 0:
        raise ConfigurationError("OpenClaw MCP registration failed")

    config_home = os.environ.get("OPENCLAW_HOME", "").strip()
    config_path = (
        Path(config_home).expanduser() if config_home else Path.home() / ".openclaw"
    ) / "openclaw.json"
    return OpenClawSetupResult(
        server_name=MCP_SERVER_NAME,
        approval_mode="host",
        config_path=config_path,
    )
