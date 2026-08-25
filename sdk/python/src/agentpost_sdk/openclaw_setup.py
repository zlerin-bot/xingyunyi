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
EXPECTED_MCP_TOOLS = frozenset(
    {
        "agentpost_ack",
        "agentpost_list_inbox",
        "agentpost_read_message",
        "agentpost_reply",
        "agentpost_resolve_recipient",
        "agentpost_search_directory",
        "agentpost_send_message",
    }
)


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


def _config_path() -> Path:
    explicit_config = os.environ.get("OPENCLAW_CONFIG_PATH", "").strip()
    if explicit_config:
        return Path(explicit_config).expanduser()
    explicit_state = os.environ.get("OPENCLAW_STATE_DIR", "").strip()
    if explicit_state:
        return Path(explicit_state).expanduser() / "openclaw.json"
    explicit_home = os.environ.get("OPENCLAW_HOME", "").strip()
    home = Path(explicit_home).expanduser() if explicit_home else Path.home()
    return home / ".openclaw" / "openclaw.json"


def _run_openclaw(
    runner: CommandRunner,
    command: list[str],
) -> CommandResult:
    try:
        return runner(
            command,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ConfigurationError("OpenClaw MCP registration could not be started") from exc


def _verify_probe(payload_text: str) -> None:
    try:
        payload = json.loads(payload_text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ConfigurationError("OpenClaw MCP verification returned malformed output") from exc
    if not isinstance(payload, dict):
        raise ConfigurationError("OpenClaw MCP verification returned malformed output")
    raw_tools = payload.get("tools")
    diagnostics = payload.get("diagnostics")
    if not isinstance(raw_tools, list) or not isinstance(diagnostics, list):
        raise ConfigurationError("OpenClaw MCP verification returned malformed output")
    discovered = {
        name.rsplit("__", 1)[-1]
        for name in raw_tools
        if isinstance(name, str) and name.rsplit("__", 1)[-1].startswith("agentpost_")
    }
    if diagnostics or not EXPECTED_MCP_TOOLS.issubset(discovered):
        raise ConfigurationError("OpenClaw could not load the AgentPost MCP tools")


def preflight_openclaw_mcp(
    *,
    openclaw_command: str | None = None,
    runner: CommandRunner = subprocess.run,
) -> str:
    """Verify OpenClaw's MCP registry before Human pairing starts."""

    resolved_openclaw = openclaw_command or shutil.which("openclaw")
    if not resolved_openclaw:
        raise ConfigurationError(
            "OpenClaw is not installed or not available on PATH",
            code="openclaw_not_available",
        )
    for subcommand in ("set", "probe"):
        completed = _run_openclaw(
            runner,
            [resolved_openclaw, "mcp", subcommand, "--help"],
        )
        if completed.returncode != 0:
            raise ConfigurationError(
                "OpenClaw must be updated to a release with MCP set and probe support",
                code="openclaw_mcp_upgrade_required",
            )
    return resolved_openclaw


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
    resolved_openclaw = preflight_openclaw_mcp(
        openclaw_command=openclaw_command,
        runner=runner,
    )

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
    completed = _run_openclaw(runner, command)
    if completed.returncode != 0:
        raise ConfigurationError("OpenClaw MCP registration failed")

    probe = _run_openclaw(
        runner,
        [resolved_openclaw, "mcp", "probe", MCP_SERVER_NAME, "--json"],
    )
    if probe.returncode != 0:
        raise ConfigurationError("OpenClaw could not load the AgentPost MCP tools")
    _verify_probe(probe.stdout)

    return OpenClawSetupResult(
        server_name=MCP_SERVER_NAME,
        approval_mode="host",
        config_path=_config_path(),
    )
