"""Cross-platform command-only STDIO launcher for 豆包工作."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from agentpost_sdk.errors import ConfigurationError

LAUNCHER_SCHEMA_VERSION = 1


def _config_path(launcher_path: Path) -> Path:
    primary = launcher_path.with_name(f"{launcher_path.name}.json")
    if primary.is_file() or launcher_path.suffix.lower() == ".exe":
        return primary
    windows_console_script = launcher_path.with_name(f"{launcher_path.name}.exe.json")
    return windows_console_script if windows_console_script.is_file() else primary


def _required_text(config: dict[str, Any], key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError("豆包工作启动器配置无效")
    return value


def _read_config(config_path: Path) -> tuple[str, str, Path, Path]:
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigurationError("豆包工作启动器配置无效") from exc
    if not isinstance(config, dict) or config.get("schema_version") != LAUNCHER_SCHEMA_VERSION:
        raise ConfigurationError("豆包工作启动器配置无效")
    server = _required_text(config, "server").strip().rstrip("/")
    profile = _required_text(config, "profile").strip()
    connector = Path(_required_text(config, "connector_command")).expanduser().resolve()
    mcp = Path(_required_text(config, "mcp_command")).expanduser().resolve()
    for command in (connector, mcp):
        if not command.is_file() or not os.access(command, os.X_OK):
            raise ConfigurationError("豆包工作启动器运行环境无效")
    return server, profile, connector, mcp


def launch_doubao_work(config_path: Path) -> int:
    """Restore the paired profile, then bridge the host's inherited STDIO to MCP."""

    server, profile, connector, mcp = _read_config(config_path)
    heartbeat = subprocess.run(
        [
            str(connector),
            "--server",
            server,
            "--profile",
            profile,
            "--connector-type",
            "doubao_work",
            "--no-browser",
            "status",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if heartbeat.returncode != 0:
        print(
            "agentpost_doubao_error code=secure_connection_unavailable",
            file=sys.stderr,
        )
        return 1
    environment = os.environ.copy()
    environment["AGENTPOST_SERVER"] = server
    environment["AGENTPOST_PROFILE"] = profile
    completed = subprocess.run([str(mcp)], env=environment, check=False)
    return completed.returncode


def main() -> int:
    try:
        return launch_doubao_work(_config_path(Path(sys.argv[0]).resolve()))
    except (ConfigurationError, OSError):
        print(
            "agentpost_doubao_error code=launcher_configuration_invalid",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
