"""WorkBuddy MCP registration without exposing the paired Agent credential."""

from __future__ import annotations

import json
import os
import secrets
import stat
from dataclasses import dataclass
from pathlib import Path

from agentpost_sdk.errors import ConfigurationError

MCP_SERVER_NAME = "agentpost"
_MAX_CONFIG_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class WorkBuddySetupResult:
    server_name: str
    approval_mode: str
    config_path: Path
    restart_required: bool = True


def _config_path(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.expanduser()
    return Path.home() / ".workbuddy" / "mcp.json"


def _read_config(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        if path.stat().st_size > _MAX_CONFIG_BYTES:
            raise ConfigurationError("WorkBuddy MCP config is too large to update safely")
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigurationError("WorkBuddy MCP config is unreadable or malformed") from exc
    if not isinstance(payload, dict):
        raise ConfigurationError("WorkBuddy MCP config must be a JSON object")
    servers = payload.get("mcpServers")
    if servers is not None and not isinstance(servers, dict):
        raise ConfigurationError("WorkBuddy MCP server registry is malformed")
    return payload


def _atomic_write(path: Path, payload: dict[str, object]) -> None:
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
        mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        raise ConfigurationError("WorkBuddy MCP config could not be updated safely") from exc
    finally:
        if "temporary" in locals():
            temporary.unlink(missing_ok=True)


def configure_workbuddy_mcp(
    *,
    server: str,
    profile: str,
    mcp_command: Path,
    config_path: Path | None = None,
) -> WorkBuddySetupResult:
    """Idempotently add AgentPost to WorkBuddy's user-level MCP registry."""

    cleaned_server = server.strip().rstrip("/")
    cleaned_profile = profile.strip()
    if not cleaned_server:
        raise ConfigurationError("AgentPost server must not be empty")
    if not cleaned_profile or len(cleaned_profile) > 200:
        raise ConfigurationError("Connector profile must contain 1-200 characters")
    executable = mcp_command.expanduser().resolve()
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise ConfigurationError("agentpost-mcp is not installed in this runtime")

    path = _config_path(config_path)
    payload = _read_config(path)
    servers = payload.setdefault("mcpServers", {})
    assert isinstance(servers, dict)
    servers[MCP_SERVER_NAME] = {
        "command": str(executable),
        "args": [],
        "env": {
            "AGENTPOST_SERVER": cleaned_server,
            "AGENTPOST_PROFILE": cleaned_profile,
        },
    }
    _atomic_write(path, payload)
    verified = _read_config(path)
    if verified.get("mcpServers", {}).get(MCP_SERVER_NAME) != servers[MCP_SERVER_NAME]:  # type: ignore[union-attr]
        raise ConfigurationError("WorkBuddy MCP registration verification failed")
    return WorkBuddySetupResult(
        server_name=MCP_SERVER_NAME,
        approval_mode="host",
        config_path=path,
    )
