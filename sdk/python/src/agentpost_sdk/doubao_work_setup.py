"""豆包工作 STDIO launcher without putting the paired credential in its form."""

from __future__ import annotations

import hashlib
import os
import secrets
import shlex
import stat
from dataclasses import dataclass
from pathlib import Path

from agentpost_sdk.errors import ConfigurationError

MCP_SERVER_NAME = "星云驿"


@dataclass(frozen=True, slots=True)
class DoubaoWorkSetupResult:
    server_name: str
    approval_mode: str
    config_path: Path
    command: Path
    transport: str = "STDIO"
    manual_registration_required: bool = True
    restart_required: bool = False


def _launcher_path(profile: str, explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.expanduser()
    suffix = hashlib.sha256(profile.encode()).hexdigest()[:12]
    return Path.home() / ".agentpost" / "launchers" / f"xingyunyi-doubao-{suffix}"


def _launcher_source(
    *,
    connector_command: Path,
    mcp_command: Path,
    server: str,
    profile: str,
) -> str:
    connector = shlex.quote(str(connector_command))
    mcp = shlex.quote(str(mcp_command))
    quoted_server = shlex.quote(server)
    quoted_profile = shlex.quote(profile)
    return f"""#!/bin/sh
set -eu
SERVER={quoted_server}
PROFILE={quoted_profile}
CONNECTOR={connector}
set -- --server "$SERVER" --profile "$PROFILE" --connector-type doubao_work --no-browser status
if ! "$CONNECTOR" "$@" >/dev/null 2>&1; then
  echo "agentpost_doubao_error code=secure_connection_unavailable" >&2
  exit 1
fi
export AGENTPOST_SERVER="$SERVER"
export AGENTPOST_PROFILE="$PROFILE"
exec {mcp}
"""


def _atomic_write_executable(path: Path, content: str) -> None:
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(path.parent, 0o700)
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o700)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o700)
    except OSError as exc:
        raise ConfigurationError("豆包工作启动器无法安全写入") from exc
    finally:
        temporary.unlink(missing_ok=True)


def configure_doubao_work_mcp(
    *,
    server: str,
    profile: str,
    mcp_command: Path,
    launcher_path: Path | None = None,
) -> DoubaoWorkSetupResult:
    """Create one command-only launcher for 豆包工作的 native STDIO connector form."""

    cleaned_server = server.strip().rstrip("/")
    cleaned_profile = profile.strip()
    if not cleaned_server:
        raise ConfigurationError("AgentPost server must not be empty")
    if not cleaned_profile or len(cleaned_profile) > 200:
        raise ConfigurationError("Connector profile must contain 1-200 characters")
    executable = mcp_command.expanduser().resolve()
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise ConfigurationError("agentpost-mcp is not installed in this runtime")
    connector = executable.with_name("agentpost-connect")
    if not connector.is_file() or not os.access(connector, os.X_OK):
        raise ConfigurationError("agentpost-connect is not installed in this runtime")

    path = _launcher_path(cleaned_profile, launcher_path)
    source = _launcher_source(
        connector_command=connector,
        mcp_command=executable,
        server=cleaned_server,
        profile=cleaned_profile,
    )
    _atomic_write_executable(path, source)
    try:
        verified = path.read_text(encoding="utf-8")
        mode = stat.S_IMODE(path.stat().st_mode)
    except (OSError, UnicodeError) as exc:
        raise ConfigurationError("豆包工作启动器验证失败") from exc
    if verified != source or mode & 0o077:
        raise ConfigurationError("豆包工作启动器验证失败")
    return DoubaoWorkSetupResult(
        server_name=MCP_SERVER_NAME,
        approval_mode="host",
        config_path=path,
        command=path,
    )
