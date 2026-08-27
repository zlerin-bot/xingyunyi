from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ALIYUN_SCRIPTS = (
    ROOT / "scripts" / "aliyun" / "prepare-release.sh",
    ROOT / "scripts" / "aliyun" / "switch-release.sh",
    ROOT / "scripts" / "aliyun" / "postflight.sh",
)


def test_aliyun_release_scripts_have_valid_bash_syntax() -> None:
    subprocess.run(["bash", "-n", *(str(path) for path in ALIYUN_SCRIPTS)], check=True)


def test_production_switch_requires_explicit_confirmation() -> None:
    completed = subprocess.run(
        [str(ALIYUN_SCRIPTS[1]), "/tmp/nonexistent-agentpost-manifest"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "confirmation_required" in completed.stderr


def test_legacy_docker_path_is_not_the_aliyun_default() -> None:
    environment = os.environ.copy()
    environment["CONFIRM_PRODUCTION_CHANGE"] = "YES"
    completed = subprocess.run(
        [str(ROOT / "scripts" / "deploy-production.sh")],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.returncode == 2
    assert "legacy Docker Compose" in completed.stderr
    assert "scripts/aliyun/switch-release.sh" in completed.stderr


def test_switch_script_preserves_verified_migration_and_rollback_guards() -> None:
    script = ALIYUN_SCRIPTS[1].read_text()

    assert "upgrade head" in script
    assert 'downgrade "${prior_schema}"' in script
    assert "automatic_rollback" in script
    assert "install -o postgres -g postgres -m 600" in script
    assert "SHA256SUMS.backup" in script
    assert "production counts invalid" in script


def test_release_switch_and_postflight_enforce_three_platform_host_contract() -> None:
    switch = ALIYUN_SCRIPTS[1].read_text()
    postflight = ALIYUN_SCRIPTS[2].read_text()

    for host_variable in (
        "CODEX",
        "WORKBUDDY",
        "DOUBAO_WORK",
        "OPENCLAW",
        "HERMES",
        "MANUS",
    ):
        assert f'"AGENTPOST_{host_variable}_SETUP_PLATFORMS": "mac,linux,windows"' in switch
    assert "public host platform contract mismatch" in postflight
    assert 'expected = ["mac", "linux", "windows"]' in postflight
    assert 'payload.get("connector_release", {}).get("version")' in postflight
    assert "public protocol contract name mismatch" in postflight
    assert 'interoperability.get("a2a") != "mapping_design_only"' in postflight
    assert "human_view_changes_agent_delivery_state" in postflight


def test_prepare_script_builds_one_workbench_upload_and_staging_command() -> None:
    script = ALIYUN_SCRIPTS[0].read_text()

    assert 'upload_name="agentpost-${version}-aliyun-upload.tar.gz"' in script
    assert "tar -czf" in script
    assert "Upload only this file in Workbench" in script
    assert "do not create it in File Navigator" in script
    assert "stage_error code=directory_exists" in script
    assert "sha256sum -c SHA256SUMS" in script
    assert "chmod 750 aliyun-switch-release.sh aliyun-postflight.sh" in script


def test_switch_and_postflight_report_progress_without_health_retry_noise() -> None:
    switch = ALIYUN_SCRIPTS[1].read_text()
    postflight = ALIYUN_SCRIPTS[2].read_text()

    assert "deploy_step=$1 at=" in switch
    assert "duration_seconds=" in switch
    assert "curl -fs --max-time 5" in switch
    assert "2>/dev/null || true" in switch
    assert "duration_seconds=" in postflight
