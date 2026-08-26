from __future__ import annotations

import stat
import subprocess
from pathlib import Path

import pytest
from agentpost_sdk.doubao_work_setup import configure_doubao_work_mcp
from agentpost_sdk.errors import ConfigurationError


def _executable(path: Path) -> Path:
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o700)
    return path


def test_doubao_work_setup_creates_one_command_only_secure_launcher(tmp_path: Path) -> None:
    mcp = _executable(tmp_path / "agentpost-mcp")
    connector = _executable(tmp_path / "agentpost-connect")
    launcher = tmp_path / "launchers" / "xingyunyi"

    result = configure_doubao_work_mcp(
        server="https://agentpost.me/",
        profile="doubao_work:test-device",
        mcp_command=mcp,
        launcher_path=launcher,
    )

    source = launcher.read_text(encoding="utf-8")
    assert result.server_name == "星云驿"
    assert result.transport == "STDIO"
    assert result.command == launcher
    assert result.manual_registration_required is True
    assert stat.S_IMODE(launcher.stat().st_mode) == 0o700
    assert source.startswith("#!/bin/sh\n")
    assert str(mcp.resolve()) in source
    assert str(connector.resolve()) in source
    assert "SERVER=https://agentpost.me" in source
    assert "PROFILE=doubao_work:test-device" in source
    assert "AGENTPOST_API_KEY" not in source
    assert "agt_" not in source


def test_doubao_work_setup_is_idempotent_and_rejects_missing_mcp(tmp_path: Path) -> None:
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


def test_doubao_work_launcher_restores_profile_heartbeats_and_execs_stdio(
    tmp_path: Path,
) -> None:
    capture = tmp_path / "heartbeat-args"
    connector = tmp_path / "agentpost-connect"
    connector.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$@" > "$DOUBAO_TEST_CAPTURE"\n',
        encoding="utf-8",
    )
    connector.chmod(0o700)
    mcp = tmp_path / "agentpost-mcp"
    mcp.write_text(
        '#!/bin/sh\nprintf "%s|%s\\n" "$AGENTPOST_SERVER" "$AGENTPOST_PROFILE"\n',
        encoding="utf-8",
    )
    mcp.chmod(0o700)
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
        env={"PATH": "/usr/bin:/bin", "DOUBAO_TEST_CAPTURE": str(capture)},
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
