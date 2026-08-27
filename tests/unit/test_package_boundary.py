from __future__ import annotations

import os
import subprocess
import sys
import tomllib
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
    assert completed.stdout.strip() == "0.1.19"


def test_server_sdk_and_mcp_versions_match_release() -> None:
    import agentpost_mcp
    import agentpost_sdk

    import agentpost

    assert {agentpost.__version__, agentpost_sdk.__version__, agentpost_mcp.__version__} == {
        "0.1.19"
    }


def test_sdist_carries_the_forced_wheel_bootstrap_source() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    configuration = tomllib.loads((repository_root / "pyproject.toml").read_text())
    forced_sources = configuration["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
    sdist_includes = configuration["tool"]["hatch"]["build"]["targets"]["sdist"]["include"]

    assert set(forced_sources).issubset(sdist_includes)
