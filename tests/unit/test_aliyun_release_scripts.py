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
