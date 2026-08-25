from __future__ import annotations

import json
from pathlib import Path

import pytest
from agentpost_sdk.errors import ConfigurationError
from agentpost_sdk.workbuddy_setup import configure_workbuddy_mcp


def _executable(tmp_path: Path) -> Path:
    command = tmp_path / "agentpost-mcp"
    command.write_text("#!/bin/sh\n", encoding="utf-8")
    command.chmod(0o700)
    return command


def test_configure_workbuddy_preserves_other_servers_and_stores_only_profile(
    tmp_path: Path,
) -> None:
    path = tmp_path / ".workbuddy" / "mcp.json"
    path.parent.mkdir()
    path.write_text(
        json.dumps({"theme": "dark", "mcpServers": {"docs": {"command": "docs-mcp"}}}),
        encoding="utf-8",
    )

    first = configure_workbuddy_mcp(
        server="https://agentpost.me/",
        profile="workbuddy:test-device",
        mcp_command=_executable(tmp_path),
        config_path=path,
    )
    second = configure_workbuddy_mcp(
        server="https://agentpost.me",
        profile="workbuddy:test-device",
        mcp_command=_executable(tmp_path),
        config_path=path,
    )

    assert first == second
    assert first.approval_mode == "host"
    assert first.restart_required is True
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["theme"] == "dark"
    assert payload["mcpServers"]["docs"] == {"command": "docs-mcp"}
    assert payload["mcpServers"]["agentpost"] == {
        "command": str(_executable(tmp_path).resolve()),
        "args": [],
        "env": {
            "AGENTPOST_SERVER": "https://agentpost.me",
            "AGENTPOST_PROFILE": "workbuddy:test-device",
        },
    }
    rendered = path.read_text(encoding="utf-8")
    assert "AGENTPOST_API_KEY" not in rendered
    assert "agt_" not in rendered


def test_configure_workbuddy_rejects_malformed_existing_config(tmp_path: Path) -> None:
    path = tmp_path / "mcp.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="must be a JSON object"):
        configure_workbuddy_mcp(
            server="https://agentpost.me",
            profile="workbuddy:test",
            mcp_command=_executable(tmp_path),
            config_path=path,
        )
