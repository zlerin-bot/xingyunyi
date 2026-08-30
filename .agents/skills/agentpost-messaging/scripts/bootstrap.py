#!/usr/bin/env python3
"""Install a pinned AgentPost Connector release and resume one requested send."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.request
import venv
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit
from uuid import UUID

AUTH_CONFIG_URL = "https://agentpost.me/api/v1/auth/config"
PUBLIC_ORIGIN = "https://agentpost.me"
MAX_CONFIG_BYTES = 128 * 1024
MINIMUM_SETUP_VERSION = (0, 1, 1)
SUPPORTED_HOSTS = frozenset({"codex", "workbuddy", "doubao_work", "openclaw", "hermes", "manus"})


class BootstrapError(RuntimeError):
    """A safe bootstrap failure without credential detail."""


class CommandResult(Protocol):
    returncode: int
    stdout: str


Runner = Callable[..., CommandResult]


@dataclass(frozen=True)
class ConnectorRelease:
    version: str
    wheel_url: str
    wheel_sha256: str


def current_platform() -> str:
    if sys.platform == "darwin":
        return "mac"
    if os.name == "nt":
        return "windows"
    if sys.platform.startswith("linux"):
        return "linux"
    raise BootstrapError("unsupported_platform")


def _version_tuple(version: str) -> tuple[int, int, int]:
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise BootstrapError("invalid_release_version")
    major, minor, patch = version.split(".")
    return int(major), int(minor), int(patch)


def parse_release(
    payload: object,
    *,
    host_name: str,
    platform_name: str,
) -> ConnectorRelease:
    if not isinstance(payload, dict):
        raise BootstrapError("invalid_release_metadata")
    if host_name not in SUPPORTED_HOSTS:
        raise BootstrapError("unsupported_host")
    host_platforms = payload.get("host_setup_platforms")
    if isinstance(host_platforms, dict):
        platforms = host_platforms.get(host_name)
    else:
        # A pre-0.1.10 server published only one shared platform gate.
        platforms = (
            [] if host_name in {"doubao_work", "manus"} else payload.get("codex_setup_platforms")
        )
    release = payload.get("connector_release")
    if not isinstance(platforms, list) or platform_name not in platforms:
        raise BootstrapError("setup_not_released_for_host_platform")
    if not isinstance(release, dict):
        raise BootstrapError("invalid_release_metadata")
    version = release.get("version")
    wheel_url = release.get("wheel_url")
    wheel_sha256 = release.get("wheel_sha256")
    if not all(isinstance(value, str) for value in (version, wheel_url, wheel_sha256)):
        raise BootstrapError("invalid_release_metadata")
    assert isinstance(version, str)
    assert isinstance(wheel_url, str)
    assert isinstance(wheel_sha256, str)
    if _version_tuple(version) < MINIMUM_SETUP_VERSION:
        raise BootstrapError("release_does_not_support_setup")
    if not re.fullmatch(
        r"https://[A-Za-z0-9.-]+(?::[0-9]{1,5})?/[A-Za-z0-9._~/-]+\.whl",
        wheel_url,
    ):
        raise BootstrapError("unsafe_wheel_url")
    if not re.fullmatch(r"[0-9a-f]{64}", wheel_sha256):
        raise BootstrapError("invalid_wheel_digest")
    if urlsplit(wheel_url).netloc != urlsplit(PUBLIC_ORIGIN).netloc:
        raise BootstrapError("wheel_origin_mismatch")
    if f"agentpost-{version}-" not in wheel_url.rsplit("/", maxsplit=1)[-1]:
        raise BootstrapError("wheel_version_mismatch")
    return ConnectorRelease(version, wheel_url, wheel_sha256)


def fetch_release(
    *,
    host_name: str,
    platform_name: str,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> ConnectorRelease:
    request = urllib.request.Request(
        AUTH_CONFIG_URL,
        headers={"Accept": "application/json", "User-Agent": "agentpost-bootstrap/0.1.1"},
    )
    try:
        with opener(request, timeout=10) as response:  # type: ignore[attr-defined]
            final_url = response.geturl()
            raw = response.read(MAX_CONFIG_BYTES + 1)
    except Exception as exc:
        raise BootstrapError("release_metadata_unavailable") from exc
    if urlsplit(final_url).netloc != urlsplit(PUBLIC_ORIGIN).netloc:
        raise BootstrapError("release_metadata_origin_mismatch")
    if len(raw) > MAX_CONFIG_BYTES:
        raise BootstrapError("release_metadata_too_large")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise BootstrapError("invalid_release_metadata") from exc
    return parse_release(payload, host_name=host_name, platform_name=platform_name)


def requested_host(argv: Sequence[str]) -> str:
    if argv[0] == "setup":
        return argv[1]
    indices = [index for index, value in enumerate(argv) if value == "--ensure-host"]
    if not indices:
        return "codex"
    if len(indices) != 1 or indices[0] + 1 >= len(argv):
        raise BootstrapError("unsupported_resume_operation")
    host_name = argv[indices[0] + 1]
    if host_name not in SUPPORTED_HOSTS:
        raise BootstrapError("unsupported_resume_operation")
    return host_name


def runtime_home(*, host_name: str, version: str) -> Path:
    configured = os.environ.get("AGENTPOST_RUNTIME_HOME", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".agentpost" / "runtimes" / host_name / version


def _runtime_commands(runtime: Path) -> tuple[Path, Path]:
    if os.name == "nt":
        return runtime / "Scripts" / "python.exe", runtime / "Scripts" / "agentpost-connect.exe"
    return runtime / "bin" / "python", runtime / "bin" / "agentpost-connect"


def _installed_version(python: Path, *, runner: Runner) -> str | None:
    if not python.is_file():
        return None
    completed = runner(
        [
            str(python),
            "-I",
            "-c",
            "import importlib.metadata as m; print(m.version('agentpost'))",
        ],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def ensure_runtime(
    release: ConnectorRelease,
    *,
    runtime: Path,
    runner: Runner = subprocess.run,
    create_venv: Callable[[Path], None] | None = None,
) -> Path:
    python, connector = _runtime_commands(runtime)
    if _installed_version(python, runner=runner) != release.version:
        if not python.is_file():
            creator = create_venv or (lambda path: venv.EnvBuilder(with_pip=True).create(path))
            creator(runtime)
            python, connector = _runtime_commands(runtime)
        pinned_wheel = f"{release.wheel_url}#sha256={release.wheel_sha256}"
        requirement = f"agentpost[mcp,connector] @ {pinned_wheel}"
        try:
            completed = runner(
                [
                    str(python),
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "--no-cache-dir",
                    "--upgrade",
                    requirement,
                ],
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise BootstrapError("connector_install_timeout") from exc
        except OSError as exc:
            raise BootstrapError("connector_install_failed") from exc
        if completed.returncode != 0:
            raise BootstrapError("connector_install_failed")
    if _installed_version(python, runner=runner) != release.version or not connector.is_file():
        raise BootstrapError("connector_install_verification_failed")
    return connector


def execute(
    argv: Sequence[str],
    *,
    fetcher: Callable[..., ConnectorRelease] = fetch_release,
    runtime: Path | None = None,
    runner: Runner = subprocess.run,
    create_venv: Callable[[Path], None] | None = None,
    workspace: Path | None = None,
) -> int:
    setup_valid = False
    if argv and argv[0] == "setup" and len(argv) in {2, 4} and argv[1] in SUPPORTED_HOSTS:
        setup_valid = len(argv) == 2
        if len(argv) == 4 and argv[2] in {"--existing-agent-id", "--new-agent-intent"}:
            try:
                UUID(argv[3])
            except ValueError:
                pass
            else:
                setup_valid = True
    if (
        not argv
        or (argv[0] == "setup" and not setup_valid)
        or argv[0] not in {"send", "send-organization", "setup"}
    ):
        raise BootstrapError("unsupported_resume_operation")
    host_name = requested_host(argv)
    platform_name = current_platform()
    release = fetcher(host_name=host_name, platform_name=platform_name)
    connector = ensure_runtime(
        release,
        runtime=runtime or runtime_home(host_name=host_name, version=release.version),
        runner=runner,
        create_venv=create_venv,
    )
    connector_argv = list(argv)
    if connector_argv[:2] == ["setup", "manus"]:
        connector_argv.extend(["--workspace", str((workspace or Path.cwd()).resolve())])
    completed = runner([str(connector), *connector_argv], check=False)
    return completed.returncode


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return execute(list(argv if argv is not None else sys.argv[1:]))
    except BootstrapError as exc:
        print(f"agentpost_bootstrap_error code={exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
