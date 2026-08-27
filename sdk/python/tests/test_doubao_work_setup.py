from __future__ import annotations

import json
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from agentpost_sdk import doubao_work_launcher
from agentpost_sdk.doubao_work_setup import configure_doubao_work_mcp
from agentpost_sdk.errors import ConfigurationError


def _executable(path: Path, source: str = "#!/bin/sh\nexit 0\n") -> Path:
    path.write_text(source, encoding="utf-8")
    path.chmod(0o700)
    return path


def _runtime(tmp_path: Path, *, windows_names: bool = False) -> tuple[Path, Path, Path]:
    suffix = ".exe" if windows_names else ""
    mcp = _executable(tmp_path / f"agentpost-mcp{suffix}")
    connector = _executable(tmp_path / f"agentpost-connect{suffix}")
    template = _executable(
        tmp_path / f"agentpost-doubao{suffix}",
        "#!/usr/bin/env python3\n"
        "from agentpost_sdk.doubao_work_launcher import main\n"
        "raise SystemExit(main())\n",
    )
    return mcp, connector, template


def test_doubao_work_setup_creates_command_only_secure_launcher_and_config(
    tmp_path: Path,
) -> None:
    mcp, connector, template = _runtime(tmp_path)
    launcher = tmp_path / "launchers" / "xingyunyi"

    result = configure_doubao_work_mcp(
        server="https://agentpost.me/",
        profile="doubao_work:test-device",
        mcp_command=mcp,
        launcher_path=launcher,
    )

    config = json.loads(result.config_path.read_text(encoding="utf-8"))
    assert result.server_name == "星云驿"
    assert result.transport == "STDIO"
    assert result.command == launcher
    assert result.config_path == launcher.with_name("xingyunyi.json")
    assert result.manual_registration_required is True
    assert stat.S_IMODE(launcher.stat().st_mode) == 0o700
    assert stat.S_IMODE(result.config_path.stat().st_mode) == 0o600
    assert launcher.read_bytes() == template.read_bytes()
    assert config == {
        "connector_command": str(connector.resolve()),
        "mcp_command": str(mcp.resolve()),
        "profile": "doubao_work:test-device",
        "schema_version": 1,
        "server": "https://agentpost.me",
    }
    serialized = result.config_path.read_text(encoding="utf-8")
    assert "AGENTPOST_API_KEY" not in serialized
    assert "agt_" not in serialized


def test_doubao_work_setup_requires_all_three_runtime_commands(tmp_path: Path) -> None:
    launcher = tmp_path / "launcher"
    with pytest.raises(ConfigurationError):
        configure_doubao_work_mcp(
            server="https://agentpost.me",
            profile="doubao_work:test-device",
            mcp_command=tmp_path / "missing",
            launcher_path=launcher,
        )

    mcp = _executable(tmp_path / "agentpost-mcp")
    _executable(tmp_path / "agentpost-connect")
    with pytest.raises(ConfigurationError, match="agentpost-doubao"):
        configure_doubao_work_mcp(
            server="https://agentpost.me",
            profile="doubao_work:test-device",
            mcp_command=mcp,
            launcher_path=launcher,
        )


def test_doubao_work_setup_is_idempotent(tmp_path: Path) -> None:
    mcp, _, _ = _runtime(tmp_path)
    launcher = tmp_path / "launcher"
    first = configure_doubao_work_mcp(
        server="https://agentpost.me",
        profile="doubao_work:test-device",
        mcp_command=mcp,
        launcher_path=launcher,
    )
    second = configure_doubao_work_mcp(
        server="https://agentpost.me",
        profile="doubao_work:test-device",
        mcp_command=mcp,
        launcher_path=launcher,
    )
    assert first == second


def test_doubao_work_setup_preserves_windows_executable_launcher(tmp_path: Path) -> None:
    mcp, _, template = _runtime(tmp_path, windows_names=True)
    launcher = tmp_path / "launchers" / "xingyunyi-doubao.exe"

    result = configure_doubao_work_mcp(
        server="https://agentpost.me",
        profile="doubao_work:windows-device",
        mcp_command=mcp,
        launcher_path=launcher,
    )

    assert result.command.suffix == ".exe"
    assert result.command.read_bytes() == template.read_bytes()
    config = json.loads(result.config_path.read_text(encoding="utf-8"))
    assert config["connector_command"].endswith("agentpost-connect.exe")
    assert config["mcp_command"].endswith("agentpost-mcp.exe")


def test_doubao_work_launcher_finds_windows_config_when_argv_strips_exe(
    tmp_path: Path,
) -> None:
    mcp, _, _ = _runtime(tmp_path, windows_names=True)
    launcher = tmp_path / "launchers" / "xingyunyi-doubao.exe"
    result = configure_doubao_work_mcp(
        server="https://agentpost.me",
        profile="doubao_work:windows-device",
        mcp_command=mcp,
        launcher_path=launcher,
    )

    stripped_argv_path = launcher.with_suffix("")
    assert not stripped_argv_path.with_name(f"{stripped_argv_path.name}.json").exists()
    assert doubao_work_launcher._config_path(stripped_argv_path) == result.config_path


def test_doubao_work_launcher_restores_profile_heartbeats_and_bridges_stdio(
    tmp_path: Path,
) -> None:
    capture = tmp_path / "heartbeat-args"
    mcp, connector, _ = _runtime(tmp_path)
    connector.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$@" > "$DOUBAO_TEST_CAPTURE"\n',
        encoding="utf-8",
    )
    mcp.write_text(
        '#!/bin/sh\nprintf "%s|%s\\n" "$AGENTPOST_SERVER" "$AGENTPOST_PROFILE"\n',
        encoding="utf-8",
    )
    launcher = tmp_path / "xingyunyi-doubao"
    configure_doubao_work_mcp(
        server="https://agentpost.me",
        profile="doubao_work:test-device",
        mcp_command=mcp,
        launcher_path=launcher,
    )

    completed = subprocess.run(
        [str(launcher)],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        env={
            "PATH": f"{Path(sys.executable).parent}:/usr/bin:/bin",
            "DOUBAO_TEST_CAPTURE": str(capture),
            "PYTHONPATH": str(Path(__file__).parents[1] / "src"),
        },
    )

    assert completed.returncode == 0
    assert completed.stdout == "https://agentpost.me|doubao_work:test-device\n"
    assert completed.stderr == ""
    assert capture.read_text(encoding="utf-8").splitlines() == [
        "--server",
        "https://agentpost.me",
        "--profile",
        "doubao_work:test-device",
        "--connector-type",
        "doubao_work",
        "--no-browser",
        "status",
    ]


def test_doubao_work_launcher_fails_closed_without_paired_vault_profile(
    tmp_path: Path,
) -> None:
    mcp, connector, _ = _runtime(tmp_path)
    connector.write_text("#!/bin/sh\nexit 2\n", encoding="utf-8")
    launcher = tmp_path / "xingyunyi-doubao"
    configure_doubao_work_mcp(
        server="https://agentpost.me",
        profile="doubao_work:test-device",
        mcp_command=mcp,
        launcher_path=launcher,
    )

    completed = subprocess.run(
        [str(launcher)],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        env={
            "PATH": f"{Path(sys.executable).parent}:/usr/bin:/bin",
            "PYTHONPATH": str(Path(__file__).parents[1] / "src"),
        },
    )

    assert completed.returncode == 1
    assert completed.stdout == ""
    assert completed.stderr == "agentpost_doubao_error code=secure_connection_unavailable\n"
