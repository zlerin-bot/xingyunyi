"""Codex host registration without exposing the paired Agent credential."""

from __future__ import annotations

import os
import re
import secrets
import shutil
import stat
import subprocess
import tomllib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from agentpost_sdk.errors import ConfigurationError

MCP_SERVER_NAME = "agentpost"
_SERVER_HEADER = f"[mcp_servers.{MCP_SERVER_NAME}]"
_APPROVAL_KEY = "default_tools_approval_mode"
_APPROVAL_LINE = f'{_APPROVAL_KEY} = "writes"\n'
_DIRECT_KEY = re.compile(rf"^\s*{_APPROVAL_KEY}\s*=", flags=re.ASCII)
_MAX_CONFIG_BYTES = 2 * 1024 * 1024


class CommandResult(Protocol):
    returncode: int


CommandRunner = Callable[..., CommandResult]


@dataclass(frozen=True, slots=True)
class CodexSetupResult:
    server_name: str
    approval_mode: str
    config_path: Path
    restart_required: bool = True


def _codex_home(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.expanduser()
    configured = os.environ.get("CODEX_HOME", "").strip()
    return Path(configured).expanduser() if configured else Path.home() / ".codex"


def _read_config(path: Path) -> str:
    try:
        if path.stat().st_size > _MAX_CONFIG_BYTES:
            raise ConfigurationError("Codex config is too large to update safely")
        text = path.read_text(encoding="utf-8")
        tomllib.loads(text)
        return text
    except FileNotFoundError as exc:
        raise ConfigurationError("Codex MCP registration did not create config.toml") from exc
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigurationError("Codex config is unreadable or malformed") from exc


def _approval_section(text: str) -> tuple[list[str], int, int]:
    lines = text.splitlines(keepends=True)
    try:
        start = next(index for index, line in enumerate(lines) if line.strip() == _SERVER_HEADER)
    except StopIteration as exc:
        raise ConfigurationError("Codex MCP registration is missing the AgentPost server") from exc
    end = next(
        (index for index in range(start + 1, len(lines)) if lines[index].lstrip().startswith("[")),
        len(lines),
    )
    return lines, start, end


def _render_writes_policy(text: str) -> str:
    lines, start, end = _approval_section(text)
    direct_keys = [index for index in range(start + 1, end) if _DIRECT_KEY.match(lines[index])]
    if len(direct_keys) > 1:
        raise ConfigurationError("Codex AgentPost MCP approval policy is ambiguous")
    if direct_keys:
        lines[direct_keys[0]] = _APPROVAL_LINE
    else:
        command_index = next(
            (
                index
                for index in range(start + 1, end)
                if lines[index].lstrip().startswith("command =")
            ),
            start,
        )
        lines.insert(command_index + 1, _APPROVAL_LINE)
    rendered = "".join(lines)
    try:
        parsed = tomllib.loads(rendered)
        server = parsed["mcp_servers"][MCP_SERVER_NAME]
    except (KeyError, TypeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigurationError("Codex AgentPost MCP config validation failed") from exc
    if server.get(_APPROVAL_KEY) != "writes":
        raise ConfigurationError("Codex AgentPost MCP write approval policy was not applied")
    return rendered


def _atomic_write_config(path: Path, text: str) -> None:
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    try:
        original_mode = stat.S_IMODE(path.stat().st_mode)
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, original_mode)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        raise ConfigurationError("Codex config could not be updated safely") from exc
    finally:
        temporary.unlink(missing_ok=True)


def _ensure_writes_policy(config_path: Path) -> None:
    current = _read_config(config_path)
    rendered = _render_writes_policy(current)
    if rendered != current:
        _atomic_write_config(config_path, rendered)


def configure_codex_mcp(
    *,
    server: str,
    profile: str,
    mcp_command: Path,
    codex_command: str | None = None,
    codex_home: Path | None = None,
    runner: CommandRunner = subprocess.run,
) -> CodexSetupResult:
    """Idempotently register AgentPost in Codex using only a vault profile reference."""

    cleaned_server = server.strip().rstrip("/")
    cleaned_profile = profile.strip()
    if not cleaned_server:
        raise ConfigurationError("AgentPost server must not be empty")
    if not cleaned_profile or len(cleaned_profile) > 200:
        raise ConfigurationError("Connector profile must contain 1-200 characters")

    executable = mcp_command.expanduser().resolve()
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise ConfigurationError("agentpost-mcp is not installed in this runtime")
    resolved_codex = codex_command or shutil.which("codex")
    if not resolved_codex:
        raise ConfigurationError("Codex CLI is not installed or not available on PATH")

    home = _codex_home(codex_home)
    try:
        home.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError as exc:
        raise ConfigurationError("Codex home could not be prepared") from exc
    environment = os.environ.copy()
    environment["CODEX_HOME"] = str(home)
    command: Sequence[str] = (
        resolved_codex,
        "mcp",
        "add",
        MCP_SERVER_NAME,
        "--env",
        f"AGENTPOST_SERVER={cleaned_server}",
        "--env",
        f"AGENTPOST_PROFILE={cleaned_profile}",
        "--",
        str(executable),
    )
    try:
        completed = runner(
            command,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env=environment,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ConfigurationError("Codex MCP registration could not be started") from exc
    if completed.returncode != 0:
        raise ConfigurationError("Codex MCP registration failed")

    config_path = home / "config.toml"
    _ensure_writes_policy(config_path)
    return CodexSetupResult(
        server_name=MCP_SERVER_NAME,
        approval_mode="writes",
        config_path=config_path,
    )
