from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = REPOSITORY_ROOT / ".agents" / "skills" / "agentpost-messaging"
PLUGIN_ROOT = REPOSITORY_ROOT / "plugins" / "agentpost"
PLUGIN_SKILL_ROOT = PLUGIN_ROOT / "skills" / "agentpost-messaging"


def _load_bootstrap() -> ModuleType:
    path = SKILL_ROOT / "scripts" / "bootstrap.py"
    spec = importlib.util.spec_from_file_location("agentpost_skill_bootstrap", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _release(bootstrap: ModuleType):
    return bootstrap.ConnectorRelease(
        version="0.1.1",
        wheel_url="https://agentpost.me/downloads/agentpost-0.1.1-py3-none-any.whl",
        wheel_sha256="a" * 64,
    )


def test_skill_is_implicitly_discoverable_and_declares_agentpost_dependency() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    metadata = yaml.safe_load((SKILL_ROOT / "agents" / "openai.yaml").read_text())

    assert skill.startswith("---\nname: agentpost-messaging\n")
    assert "请连接我的星云驿" in skill
    assert "scripts/bootstrap.py setup <current-host>" in skill
    assert "Treat a partially loaded or outdated AgentPost MCP as unavailable" in skill
    assert "never report\n   `not_found` from that legacy path" in skill
    assert "upgrades to the server-pinned release and resumes the send" in skill
    assert metadata["policy"]["allow_implicit_invocation"] is True
    assert metadata["dependencies"]["tools"] == [
        {
            "type": "mcp",
            "value": "agentpost",
            "description": "AgentPost persistent messaging and directory tools",
            "transport": "stdio",
        }
    ]


def test_plugin_packages_the_same_implicit_skill_without_machine_specific_mcp_config() -> None:
    manifest = json.loads(
        (PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )

    assert manifest["name"] == "agentpost"
    plugin_version, separator, cachebuster = manifest["version"].partition("+")
    assert plugin_version == "0.1.3"
    assert separator == "+"
    assert cachebuster.startswith("codex.")
    assert manifest["skills"] == "./skills/"
    assert "mcpServers" not in manifest
    assert not (PLUGIN_ROOT / ".mcp.json").exists()
    for relative_path in (
        Path("SKILL.md"),
        Path("agents/openai.yaml"),
        Path("scripts/bootstrap.py"),
    ):
        assert (PLUGIN_SKILL_ROOT / relative_path).read_bytes() == (
            SKILL_ROOT / relative_path
        ).read_bytes()


def test_bootstrap_imports_with_the_system_python_used_by_the_copyable_prompt() -> None:
    system_python = Path("/usr/bin/python3")
    if not system_python.is_file():
        pytest.skip("macOS system python is not present on this host")
    completed = subprocess.run(
        [str(system_python), str(SKILL_ROOT / "scripts" / "bootstrap.py")],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert completed.returncode == 1
    assert "agentpost_bootstrap_error code=unsupported_resume_operation" in completed.stderr
    assert "Traceback" not in completed.stderr


def test_release_metadata_must_enable_platform_and_match_trusted_origin() -> None:
    bootstrap = _load_bootstrap()
    payload = {
        "codex_setup_platforms": ["mac"],
        "connector_release": {
            "version": "0.1.1",
            "wheel_url": "https://agentpost.me/downloads/agentpost-0.1.1-py3-none-any.whl",
            "wheel_sha256": "a" * 64,
        },
    }

    assert bootstrap.parse_release(payload, platform_name="mac") == _release(bootstrap)
    with pytest.raises(bootstrap.BootstrapError, match="setup_not_released"):
        bootstrap.parse_release(payload, platform_name="windows")

    payload["connector_release"]["wheel_url"] = (
        "https://example.com/downloads/agentpost-0.1.1-py3-none-any.whl"
    )
    with pytest.raises(bootstrap.BootstrapError, match="wheel_origin_mismatch"):
        bootstrap.parse_release(payload, platform_name="mac")


def test_bootstrap_installs_hash_pinned_release_once_and_resumes_original_send(
    tmp_path: Path,
) -> None:
    bootstrap = _load_bootstrap()
    runtime = tmp_path / "runtime"
    state = {"installed": False}
    calls: list[tuple[str, ...]] = []

    def create_venv(path: Path) -> None:
        bin_dir = path / "bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "python").write_text("", encoding="utf-8")

    def runner(command, **_kwargs):
        normalized = tuple(str(item) for item in command)
        calls.append(normalized)
        if "-I" in normalized:
            return SimpleNamespace(
                returncode=0 if state["installed"] else 1,
                stdout="0.1.1\n" if state["installed"] else "",
            )
        if "pip" in normalized:
            assert normalized[-1].endswith(f"#sha256={'a' * 64}")
            state["installed"] = True
            (runtime / "bin" / "agentpost-connect").write_text("", encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="")
        return SimpleNamespace(returncode=0, stdout="")

    operation = [
        "send",
        "--ensure-host",
        "codex",
        "--recipient",
        "张三",
        "--body",
        "请查收报告。",
    ]
    exit_code = bootstrap.execute(
        operation,
        fetcher=lambda **_kwargs: _release(bootstrap),
        runtime=runtime,
        runner=runner,
        create_venv=create_venv,
    )

    assert exit_code == 0
    assert calls[-1] == (str(runtime / "bin" / "agentpost-connect"), *operation)
    assert sum("pip" in call for call in calls) == 1


@pytest.mark.parametrize("host", ["codex", "workbuddy", "openclaw"])
def test_bootstrap_connection_prompt_installs_once_and_runs_host_setup(
    tmp_path: Path,
    host: str,
) -> None:
    bootstrap = _load_bootstrap()
    runtime = tmp_path / "runtime"
    state = {"installed": False}
    calls: list[tuple[str, ...]] = []

    def create_venv(path: Path) -> None:
        bin_dir = path / "bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "python").write_text("", encoding="utf-8")

    def runner(command, **_kwargs):
        normalized = tuple(str(item) for item in command)
        calls.append(normalized)
        if "-I" in normalized:
            return SimpleNamespace(
                returncode=0 if state["installed"] else 1,
                stdout="0.1.1\n" if state["installed"] else "",
            )
        if "pip" in normalized:
            state["installed"] = True
            (runtime / "bin" / "agentpost-connect").write_text("", encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="")
        return SimpleNamespace(returncode=0, stdout="")

    assert (
        bootstrap.execute(
            ["setup", host],
            fetcher=lambda **_kwargs: _release(bootstrap),
            runtime=runtime,
            runner=runner,
            create_venv=create_venv,
        )
        == 0
    )

    assert calls[-1] == (str(runtime / "bin" / "agentpost-connect"), "setup", host)
    assert sum("pip" in call for call in calls) == 1


def test_bootstrap_rejects_arbitrary_setup_targets() -> None:
    bootstrap = _load_bootstrap()
    with pytest.raises(bootstrap.BootstrapError, match="unsupported_resume_operation"):
        bootstrap.execute(["setup", "unknown"])
