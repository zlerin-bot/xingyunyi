"""Manus STDIO setup without placing paired credentials in its connector form."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import stat
from dataclasses import dataclass
from pathlib import Path

from agentpost_sdk.errors import ConfigurationError

MCP_SERVER_NAME = "星云驿"
LAUNCHER_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class ManusSetupResult:
    server_name: str
    approval_mode: str
    config_path: Path
    command: Path
    transport: str = "STDIO"
    manual_registration_required: bool = True
    restart_required: bool = False


def _launcher_path(profile: str, explicit: Path | None, *, windows: bool) -> Path:
    if explicit is not None:
        return explicit.expanduser()
    suffix = hashlib.sha256(profile.encode()).hexdigest()[:12]
    executable_suffix = ".exe" if windows else ""
    return Path.home() / ".agentpost" / "launchers" / f"xingyunyi-manus-{suffix}{executable_suffix}"


def _config_path(launcher_path: Path) -> Path:
    return launcher_path.with_name(f"{launcher_path.name}.json")


def _atomic_write(path: Path, content: bytes, *, mode: int) -> None:
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if os.name != "nt":
            os.chmod(path.parent, 0o700)
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        os.chmod(path, mode)
    except OSError as exc:
        raise ConfigurationError("Manus launcher could not be written securely") from exc
    finally:
        temporary.unlink(missing_ok=True)


def _installed_command(mcp_command: Path, name: str) -> Path:
    suffix = ".exe" if mcp_command.suffix.lower() == ".exe" else ""
    return mcp_command.with_name(f"{name}{suffix}")


def _validate_installed_command(path: Path, error: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise ConfigurationError(error)
    return resolved


def configure_manus_mcp(
    *,
    server: str,
    profile: str,
    mcp_command: Path,
    launcher_path: Path | None = None,
) -> ManusSetupResult:
    """Create a command-only native launcher for Manus on macOS or Windows."""

    cleaned_server = server.strip().rstrip("/")
    cleaned_profile = profile.strip()
    if not cleaned_server:
        raise ConfigurationError("AgentPost server must not be empty")
    if not cleaned_profile or len(cleaned_profile) > 200:
        raise ConfigurationError("Connector profile must contain 1-200 characters")

    executable = _validate_installed_command(mcp_command, "agentpost-mcp is not installed")
    connector = _validate_installed_command(
        _installed_command(executable, "agentpost-connect"),
        "agentpost-connect is not installed",
    )
    launcher_template = _validate_installed_command(
        _installed_command(executable, "agentpost-manus"),
        "agentpost-manus is not installed",
    )
    path = _launcher_path(
        cleaned_profile,
        launcher_path,
        windows=executable.suffix.lower() == ".exe",
    )
    config_path = _config_path(path)
    config = {
        "connector_command": str(connector),
        "mcp_command": str(executable),
        "profile": cleaned_profile,
        "schema_version": LAUNCHER_SCHEMA_VERSION,
        "server": cleaned_server,
    }
    config_bytes = (
        json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    try:
        template_bytes = launcher_template.read_bytes()
    except OSError as exc:
        raise ConfigurationError("Manus launcher could not be read securely") from exc
    _atomic_write(path, template_bytes, mode=0o700)
    _atomic_write(config_path, config_bytes, mode=0o600)

    try:
        launcher_verified = path.read_bytes()
        config_verified = config_path.read_bytes()
        launcher_mode = stat.S_IMODE(path.stat().st_mode)
        config_mode = stat.S_IMODE(config_path.stat().st_mode)
    except OSError as exc:
        raise ConfigurationError("Manus launcher verification failed") from exc
    insecure_mode = os.name != "nt" and (launcher_mode & 0o077 or config_mode & 0o077)
    if launcher_verified != template_bytes or config_verified != config_bytes or insecure_mode:
        raise ConfigurationError("Manus launcher verification failed")
    return ManusSetupResult(
        server_name=MCP_SERVER_NAME,
        approval_mode="host",
        config_path=config_path,
        command=path,
    )
