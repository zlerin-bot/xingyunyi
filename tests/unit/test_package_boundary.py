from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_server_package_metadata_import_does_not_require_sdk(tmp_path: Path) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(repository_root / "src")

    completed = subprocess.run(
        [
            sys.executable,
            "-S",
            "-c",
            "import agentpost; print(agentpost.__version__)",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "0.1.0"
