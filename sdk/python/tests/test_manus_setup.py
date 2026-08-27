from __future__ import annotations

import hashlib
import json
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from agentpost_sdk.errors import ConfigurationError
from agentpost_sdk.manus_setup import configure_manus_local_folder, configure_manus_mcp


def _executable(path: Path, source: str = "#!/bin/sh\nexit 0\n") -> Path:
    path.write_text(source, encoding="utf-8")
    path.chmod(0o700)
    return path


def _runtime(tmp_path: Path, *, windows: bool = False) -> tuple[Path, Path, Path]:
    suffix = ".exe" if windows else ""
    mcp = _executable(tmp_path / f"agentpost-mcp{suffix}")
    connector = _executable(tmp_path / f"agentpost-connect{suffix}")
    launcher = _executable(
        tmp_path / f"agentpost-manus{suffix}",
        "#!/usr/bin/env python3\n"
        "from agentpost_sdk.manus_launcher import main\n"
        "raise SystemExit(main())\n",
    )
    return mcp, connector, launcher


def _local_runtime(tmp_path: Path) -> tuple[Path, Path]:
    mcp = _executable(tmp_path / "agentpost-mcp")
    adapter = _executable(
        tmp_path / "agentpost-manus-folder",
        "#!/usr/bin/env python3\nfrom agentpost_sdk.manus_local_adapter import main\n",
    )
    return mcp, adapter


def test_manus_local_folder_setup_creates_secret_free_verified_files(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    mcp, adapter = _local_runtime(runtime)
    workspace = tmp_path / "manus-workspace"
    workspace.mkdir()

    result = configure_manus_local_folder(
        server="https://agentpost.me/",
        profile="manus:test-device",
        expected_agent_address="020-manus-001@agentpost.me",
        mcp_command=mcp,
        workspace_path=workspace,
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert result.mode == "local_folder"
    assert result.command.read_bytes() == adapter.read_bytes()
    assert "# 星云驿 Manus 本地文件夹" in result.agents_path.read_text(encoding="utf-8")
    assert stat.S_IMODE(result.command.stat().st_mode) == 0o700
    assert stat.S_IMODE(result.agents_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(result.manifest_path.stat().st_mode) == 0o600
    assert manifest["expected_agent_address"] == "020-manus-001@agentpost.me"
    assert manifest["adapter_sha256"] == hashlib.sha256(adapter.read_bytes()).hexdigest()
    assert manifest["agents_sha256"] == hashlib.sha256(result.agents_path.read_bytes()).hexdigest()
    serialized = result.manifest_path.read_text(encoding="utf-8")
    assert "AGENTPOST_API_KEY" not in serialized
    assert "agt_" not in serialized
    assert "new task" not in result.first_task_prompt.lower()
    assert "manus_task_mount_stale" in result.first_task_prompt


def test_manus_local_folder_setup_refuses_incomplete_or_unmanaged_bundle(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    mcp, _ = _local_runtime(runtime)
    workspace = tmp_path / "manus-workspace"
    workspace.mkdir()
    (workspace / "AGENTS.md").write_text("user-owned instructions\n", encoding="utf-8")

    with pytest.raises(ConfigurationError) as exc_info:
        configure_manus_local_folder(
            server="https://agentpost.me",
            profile="manus:test-device",
            expected_agent_address="020-manus-001@agentpost.me",
            mcp_command=mcp,
            workspace_path=workspace,
        )

    assert exc_info.value.code == "manus_local_adapter_conflict"


def test_manus_setup_creates_secret_free_command_only_launcher(tmp_path: Path) -> None:
    mcp, connector, template = _runtime(tmp_path)
    launcher = tmp_path / "launchers" / "xingyunyi-manus"
    result = configure_manus_mcp(
        server="https://agentpost.me/",
        profile="manus:test-device",
        mcp_command=mcp,
        launcher_path=launcher,
    )
    config = json.loads(result.config_path.read_text(encoding="utf-8"))
    assert result.transport == "STDIO"
    assert result.manual_registration_required is True
    assert result.command.read_bytes() == template.read_bytes()
    assert stat.S_IMODE(result.command.stat().st_mode) == 0o700
    assert stat.S_IMODE(result.config_path.stat().st_mode) == 0o600
    assert config == {
        "connector_command": str(connector.resolve()),
        "mcp_command": str(mcp.resolve()),
        "profile": "manus:test-device",
        "schema_version": 1,
        "server": "https://agentpost.me",
    }
    serialized = result.config_path.read_text(encoding="utf-8")
    assert "AGENTPOST_API_KEY" not in serialized
    assert "agt_" not in serialized


def test_manus_setup_preserves_windows_console_executable(tmp_path: Path) -> None:
    mcp, _, template = _runtime(tmp_path, windows=True)
    launcher = tmp_path / "launchers" / "xingyunyi-manus.exe"
    result = configure_manus_mcp(
        server="https://agentpost.me",
        profile="manus:windows-device",
        mcp_command=mcp,
        launcher_path=launcher,
    )
    config = json.loads(result.config_path.read_text(encoding="utf-8"))
    assert result.command.suffix == ".exe"
    assert result.command.read_bytes() == template.read_bytes()
    assert config["connector_command"].endswith("agentpost-connect.exe")
    assert config["mcp_command"].endswith("agentpost-mcp.exe")


def test_manus_launcher_restores_vault_profile_and_bridges_stdio(tmp_path: Path) -> None:
    capture = tmp_path / "heartbeat-args"
    mcp, connector, _ = _runtime(tmp_path)
    connector.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$@" > "$MANUS_TEST_CAPTURE"\n', encoding="utf-8"
    )
    mcp.write_text(
        '#!/bin/sh\nprintf "%s|%s\\n" "$AGENTPOST_SERVER" "$AGENTPOST_PROFILE"\n',
        encoding="utf-8",
    )
    launcher = tmp_path / "xingyunyi-manus"
    configure_manus_mcp(
        server="https://agentpost.me",
        profile="manus:test-device",
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
            "MANUS_TEST_CAPTURE": str(capture),
            "PYTHONPATH": str(Path(__file__).parents[1] / "src"),
        },
    )
    assert completed.returncode == 0
    assert completed.stdout == "https://agentpost.me|manus:test-device\n"
    assert capture.read_text(encoding="utf-8").splitlines()[-4:] == [
        "--connector-type",
        "manus",
        "--no-browser",
        "status",
    ]


def test_manus_launcher_fails_closed_when_vault_profile_is_missing(tmp_path: Path) -> None:
    mcp, connector, _ = _runtime(tmp_path)
    connector.write_text("#!/bin/sh\nexit 2\n", encoding="utf-8")
    launcher = tmp_path / "xingyunyi-manus"
    configure_manus_mcp(
        server="https://agentpost.me",
        profile="manus:test-device",
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
    assert completed.stderr == "agentpost_manus_error code=secure_connection_unavailable\n"
