from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select

from agentpost.access.models import AccessRule
from agentpost.config import Settings
from agentpost.control.models import (
    HumanAccessKey,
    HumanActionAudit,
    HumanSession,
    HumanThreadView,
    HumanUser,
)
from agentpost.db import Database
from agentpost.identity.models import Agent
from agentpost.main import create_app
from agentpost.messaging.models import Delivery, Message
from agentpost.onboarding.models import AgentConnectorBinding, ConnectorInstance

ADMIN_KEY = "admin-secret-admin-secret-admin-secret"


def _control_client(settings: Settings, database: Database) -> TestClient:
    protected = Settings(
        environment="test",
        database_url=settings.database_url,
        storage_path=settings.storage_path,
        api_key_pepper="test-agent-pepper",
        human_api_key_pepper="test-human-pepper",
        cursor_secret="test-cursor-secret",
        registration_token="register-secret",
        admin_token=ADMIN_KEY,
        remote_mcp_oauth_enabled=settings.remote_mcp_oauth_enabled,
        doubao_work_remote_mcp_enabled=settings.doubao_work_remote_mcp_enabled,
        manus_remote_mcp_enabled=settings.manus_remote_mcp_enabled,
        codex_setup_platforms=settings.codex_setup_platforms,
        workbuddy_setup_platforms=settings.workbuddy_setup_platforms,
        doubao_work_setup_platforms=settings.doubao_work_setup_platforms,
        manus_setup_platforms=settings.manus_setup_platforms,
        openclaw_setup_platforms=settings.openclaw_setup_platforms,
        hermes_setup_platforms=settings.hermes_setup_platforms,
        connector_release_version=settings.connector_release_version,
        connector_wheel_url=settings.connector_wheel_url,
        connector_wheel_sha256=settings.connector_wheel_sha256,
        public_base_url=settings.public_base_url,
        remote_mcp_resource_url=settings.remote_mcp_resource_url,
        log_level="WARNING",
    )
    return TestClient(create_app(settings=protected, database=database))


def _admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {ADMIN_KEY}"}


def _create_agent(client: TestClient, address: str, name: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/agents",
        headers={"X-Registration-Token": "register-secret"},
        json={
            "address": address,
            "display_name": name,
            "capabilities": ["document-analysis"],
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_human(client: TestClient, email: str, name: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/admin/humans",
        headers=_admin_headers(),
        json={"email": email, "display_name": name},
    )
    assert response.status_code == 201
    return response.json()


def _grant(
    client: TestClient,
    *,
    human_id: str,
    agent_id: str,
    role: str,
) -> None:
    response = client.put(
        f"/api/v1/admin/humans/{human_id}/agents/{agent_id}",
        headers=_admin_headers(),
        json={"role": role},
    )
    assert response.status_code == 200
    assert response.json()["role"] == role


def test_orbit_site_is_branded_and_does_not_persist_credentials(
    client: TestClient,
) -> None:
    home = client.get("/")
    orbit = client.get("/orbit")
    script = client.get("/orbit/app.js")
    stylesheet = client.get("/orbit/styles.css")
    logo = client.get("/orbit/xingyun-relay-logo.png")
    auth_config = client.get("/api/v1/auth/config")

    assert home.status_code == orbit.status_code == 200
    header = orbit.text.split('<header class="topbar">', 1)[1].split("</header>", 1)[0]
    assert "星云驿" in orbit.text
    assert "AgentPost · 星轨" in header
    assert 'id="brand-mark-gradient"' in header
    assert "plane-switch" not in header
    assert "星轨看协作" not in header
    assert "云驿管 Agent" not in header
    assert "设置管账户" not in header
    assert 'data-module="orbit"' in orbit.text
    assert 'data-module="relay"' in orbit.text
    assert 'data-module="settings"' in orbit.text
    assert "对话与协作" in orbit.text
    assert "Agent 总览" in orbit.text
    assert "个人资料" in orbit.text
    assert orbit.headers["Cache-Control"] == "no-store"
    assert "default-src 'none'" in orbit.headers["Content-Security-Policy"]
    assert "img-src 'self'" in orbit.headers["Content-Security-Policy"]
    assert "frame-src 'self'" in orbit.headers["Content-Security-Policy"]
    assert orbit.headers["X-Content-Type-Options"] == "nosniff"
    assert script.status_code == stylesheet.status_code == 200
    assert logo.status_code == 200
    assert logo.headers["Content-Type"] == "image/png"
    assert logo.headers["Cache-Control"] == "no-store"
    assert logo.headers["X-Content-Type-Options"] == "nosniff"
    assert logo.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert auth_config.status_code == 200
    assert auth_config.json()["managed_agent_domain"] == "agents.local"
    assert auth_config.json()["codex_setup_platforms"] == []
    assert auth_config.json()["host_setup_platforms"] == {
        "codex": [],
        "workbuddy": [],
        "doubao_work": [],
        "manus": [],
        "openclaw": [],
        "hermes": [],
    }
    assert auth_config.json()["host_connection_modes"] == {
        "workbuddy": "unavailable",
        "doubao_work": "unavailable",
        "openclaw": "unavailable",
        "hermes": "unavailable",
        "codex": "unavailable",
        "manus": "unavailable",
    }
    assert auth_config.json()["connector_release"] == {
        "version": "0.1.0",
        "wheel_url": "https://agentpost.me/downloads/agentpost-0.1.0-py3-none-any.whl",
        "wheel_sha256": "1fc3f42e8c1141ce65481778587544fc9bf441438c852c0332594ab24a75fdf7",
    }
    assert auth_config.json()["protocol_contract_url"] == (
        "http://127.0.0.1:8000/api/v1/protocol/contract"
    )
    assert auth_config.json()["protocol_contract_version"] == "0.1"
    combined = f"{orbit.text}\n{script.text}".casefold()
    assert "localstorage" not in combined
    assert "sessionstorage" not in combined
    assert "innerhtml" not in combined
    assert "document.cookie" not in combined
    assert "state.humankey" not in combined
    assert '"/api/v1/orbit/session"' in script.text
    assert "approval-access-key" in orbit.text
    assert "approval-requests" in script.text
    assert "X-CSRF-Token" in script.text
    assert "X-Human-Confirmation" in script.text
    assert "crypto.randomUUID()" in script.text
    assert 'elements.approvalAccessKey.value = ""' in script.text
    assert '"/api/v1/auth/login"' in script.text
    assert '"/api/v1/auth/register"' in script.text
    assert '"/api/v1/auth/recover"' in script.text
    assert '"/api/v1/orbit/security/totp/setup"' in script.text
    assert '"/api/v1/orbit/security/human-keys/rotate"' in script.text
    assert "clearSensitiveInputs();" in script.text
    assert "login-password" in orbit.text
    assert "双重验证验证码（已开启时填写）" in orbit.text
    assert "恢复码每枚只能使用一次" in orbit.text
    assert "使用单位统一登录（SSO）" in orbit.text
    assert 'id="legacy-entry"' not in orbit.text
    assert 'id="human-access-key"' not in orbit.text
    assert "旧版集成凭证（高级）" in orbit.text
    assert "recovery-dialog" in orbit.text
    assert "mfa-dialog" in orbit.text
    assert "pairing-address-domain" in orbit.text
    assert "只填写 @ 前面的部分" in orbit.text
    assert 'pattern="[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?"' in orbit.text
    assert "你现在要连接哪个 Agent" in orbit.text
    assert "复制接入码" in orbit.text
    assert "不用准备任何技术信息" in orbit.text
    assert "连接新的 Agent" in orbit.text
    assert 'data-connector-type="codex"' in orbit.text
    assert 'data-connector-type="workbuddy"' in orbit.text
    assert 'data-connector-type="doubao_work"' in orbit.text
    assert 'data-connector-type="openclaw"' in orbit.text
    assert 'data-connector-type="manus"' in orbit.text
    assert 'data-connector-type="hermes"' in orbit.text
    assert "AP-CODEX-V1" in script.text
    assert "AP-DOUBAO-WORK-V1" in script.text
    assert "AP-MANUS-V1" in script.text
    assert "AP-HERMES-V1" in script.text
    assert "https://agentpost.me/connect/${host}" in script.text
    assert "请先选择要连接的 Agent" in script.text
    assert "复制安装命令" not in orbit.text
    assert "复制连接命令" not in orbit.text
    assert "选择你正在使用的工具" not in orbit.text
    assert "复制并运行两条命令" not in script.text
    assert "navigator.clipboard.writeText" in script.text
    assert "copyPairingPrompt" in script.text
    assert "copyPairingCommand" not in script.text
    assert "pairingCommands" not in script.text
    assert "canonicalPairingLocalId" in script.text
    assert "pairingPayloadProblem" in script.text
    assert ".split(/[,，]/)" in script.text
    assert "Agent 地址格式不正确" in script.text
    assert "AGENTPOST_API_KEY" not in orbit.text
    assert "agt_" not in orbit.text
    assert "账户安全" in orbit.text
    assert "组织与成员" in orbit.text
    assert "organization-list" in orbit.text
    assert "open-organization-create" in orbit.text
    assert "organization-manage-dialog" in orbit.text
    assert "organization-invitation-dialog" in orbit.text
    assert "加入前请确认组织、角色和权限范围" in orbit.text
    assert '"/api/v1/orbit/organization-invitations/preview"' in script.text
    assert '"/api/v1/orbit/organization-invitations/accept"' in script.text
    assert "organization-invitation" in script.text
    assert "history.replaceState" in script.text
    assert "organization-domain-name" in orbit.text
    assert "/domains/" in script.text
    assert "organizationDomainProofs.clear()" in script.text
    assert "单位域名验证" in orbit.text
    assert "Agent 连接" in orbit.text
    assert '<label for="pairing-handle">短名称</label>' in orbit.text
    assert 'id="pairing-handle-help"' in orbit.text
    assert "1–32 个中文、英文字母或数字" in orbit.text
    assert 'id="pairing-mfa"' not in orbit.text
    assert "handle-dialog" in orbit.text
    assert "设置 Agent 短名称" in orbit.text
    assert "pairing-handle" in orbit.text
    assert "系统会按 Agent 平台自动填写" in orbit.text
    assert "/api/v1/orbit/agents/${encodeURIComponent(agentId)}/handle" in script.text
    assert "/api/v1/orbit/agents/${encodeURIComponent(agent.id)}/default" in script.text
    assert "设为默认 Agent" in orbit.text
    assert "does-not-exist@agentpost.me" not in script.text
    assert "查看底层身份" in script.text
    assert "修改短名称" in script.text
    assert "pairing-dialog" in orbit.text
    assert "revoke-dialog" in orbit.text
    assert "/api/v1/orbit/pairings/" in script.text
    assert "/api/v1/orbit/connectors" in script.text
    assert "pairing-existing-agent" in orbit.text
    assert "existing_agent_id" in script.text
    assert "pairing-target-summary" in orbit.text
    assert "create_new_agent" in script.text
    assert "owned.length === 1" not in script.text
    assert 'state.pairingTargetResolution = "automatic-new"' in script.text
    assert "requested_existing_agent_id" in script.text
    assert "不会替换你已有的任何 Agent" in script.text
    assert "delete-agent-dialog" in orbit.text
    assert "重新连接" in script.text
    assert "断开" in script.text
    assert "删除 Agent" in orbit.text
    assert "过去的连接记录折叠保存" in orbit.text
    assert "查看 ${historicalConnectors.length} 条历史连接记录" in script.text
    assert "不是多个可删除的 Agent" in script.text
    assert "等待 Agent 完成本机连接" in script.text
    assert 'connector.connection_state === "connected"' in script.text
    assert "现在不能收发消息" in script.text
    assert "connector-history-grid" in stylesheet.text
    assert "只需选择一次" in orbit.text
    assert "last_heartbeat_at" in script.text
    assert 'delivered: "已送达"' in script.text
    assert 'read: "Agent 已读取"' in script.text
    assert 'acked: "Agent 已确认收到"' in script.text
    assert "新动态 · 待接入" not in orbit.text
    assert "Human 已查看" not in orbit.text
    assert "chat-composer" not in orbit.text
    assert "按每个对话查看 Agent 之间的全部往来" in orbit.text
    assert "搜索有权查看的对话" in orbit.text
    assert "/api/v1/orbit/threads" in script.text
    assert "放心查看，不会影响 Agent 的处理进度" in orbit.text
    assert "暂不支持从这里直接回复" in orbit.text
    assert "发送自：" in script.text
    assert "发送给：" in script.text
    assert "owner_display_name" in script.text
    assert "/api/v1/orbit/attachments/" in script.text
    assert "打开 PDF" in script.text
    assert "安全预览" in script.text
    assert 'sandbox=""' in orbit.text
    assert "Agent 与连接状态" in orbit.text
    assert "等待 Agent" in orbit.text
    assert "连接异常" in orbit.text
    assert "重新连接这个 Agent" in orbit.text
    assert "权限与关系" in orbit.text
    assert "删除采用软删除" in orbit.text
    assert "可执行的操作以你的实际权限为准" in script.text
    assert "current_connector_last_heartbeat_at" in script.text
    assert "agent-workspace-mode:not(.agent-detail-open)" in stylesheet.text
    assert "activateRoute" in script.text
    assert "history.pushState" in script.text
    assert ".primary-navigation" in stylesheet.text
    assert ".context-sidebar" in stylesheet.text
    assert "position: fixed" in stylesheet.text
    assert "长期凭证由本地连接器自动领取" in script.text
    assert 'elements.pairingAccessKey.value = ""' in script.text
    assert 'elements.revokeAccessKey.value = ""' in script.text
    assert ".welcome-shell[hidden]" in stylesheet.text
    assert "max-height: calc(100dvh - 32px)" in stylesheet.text


def test_agent_facing_connection_contract_is_public_pinned_and_host_specific(
    client: TestClient,
) -> None:
    bootstrap = client.get("/connect/bootstrap.py")
    assert bootstrap.status_code == 200
    assert bootstrap.headers["Content-Type"].startswith("text/x-python")
    assert len(bootstrap.headers["X-AgentPost-Bootstrap-SHA256"]) == 64
    assert "SUPPORTED_HOSTS" in bootstrap.text
    assert "AGENTPOST_API_KEY" not in bootstrap.text

    for host, code, name in (
        ("codex", "AP-CODEX-V1", "Codex"),
        ("workbuddy", "AP-WORKBUDDY-V1", "WorkBuddy"),
        ("openclaw", "AP-OPENCLAW-V1", "OpenClaw"),
        ("hermes", "AP-HERMES-V1", "Hermes"),
    ):
        instructions = client.get(f"/connect/{host}")
        assert instructions.status_code == 200
        assert instructions.headers["X-AgentPost-Connection-Code"] == code
        assert f"target_host={host}" in instructions.text
        assert f"target_name={name}" in instructions.text
        assert "protocol_contract_url=" in instructions.text
        assert "protocol_contract_version=0.1" in instructions.text
        assert "contract=AGENTPOST_AGENT_INTEGRATION" in instructions.text
        assert "A2A is mapping_design_only" in instructions.text
        assert f"setup {host}" in instructions.text
        assert bootstrap.headers["X-AgentPost-Bootstrap-SHA256"] in instructions.text
        assert "at most one grouped system approval" in instructions.text
        assert "one 星轨 browser authorization" in instructions.text
        assert "long-lived credential" in instructions.text
        if host == "openclaw":
            assert "headless cloud server" in instructions.text
            assert "plaintext token file" in instructions.text

        target = "5a7044c7-6a5e-48e9-90dd-78680c91dcb9"
        reconnect = client.get(f"/connect/{host}?agent={target}")
        assert reconnect.status_code == 200
        assert f"setup {host} --existing-agent-id {target}" in reconnect.text
        assert "Preserve that Agent's durable identity" in reconnect.text

        intent = "40000000-0000-0000-0000-000000000001"
        new_agent = client.get(f"/connect/{host}?new={intent}")
        assert new_agent.status_code == 200
        assert f"setup {host} --new-agent-intent {intent}" in new_agent.text
        assert "isolate the local OS-vault profile" in new_agent.text

    assert client.get("/connect/unknown").status_code == 422
    assert client.get("/connect/codex?agent=not-a-uuid").status_code == 422
    assert (
        client.get(
            "/connect/codex"
            "?agent=5a7044c7-6a5e-48e9-90dd-78680c91dcb9"
            "&new=40000000-0000-0000-0000-000000000001"
        ).status_code
        == 422
    )


def test_manus_connection_contract_keeps_remote_fallback_fail_closed(
    client: TestClient,
    settings: Settings,
    database: Database,
) -> None:
    unavailable = client.get("/connect/manus?new=40000000-0000-0000-0000-000000000001")
    assert unavailable.status_code == 409
    assert "manus_remote_mcp_not_released" in unavailable.text
    assert "API key" in unavailable.text

    staged = Settings(
        environment="test",
        database_url=settings.database_url,
        storage_path=settings.storage_path,
        remote_mcp_oauth_enabled=True,
        manus_remote_mcp_enabled=True,
        public_base_url="https://agentpost.example",
        remote_mcp_resource_url="https://agentpost.example/mcp",
        log_level="WARNING",
    )
    with _control_client(staged, database) as remote_client:
        instructions = remote_client.get("/connect/manus?new=40000000-0000-0000-0000-000000000001")
        reconnect = remote_client.get("/connect/manus?agent=5a7044c7-6a5e-48e9-90dd-78680c91dcb9")

    assert instructions.status_code == 200
    assert instructions.headers["X-AgentPost-Connection-Code"] == "AP-MANUS-V1"
    assert "target_host=manus" in instructions.text
    assert "connection_mode=remote_mcp_oauth" in instructions.text
    assert (
        "mcp_url=https://agentpost.example/mcp/connect/"
        "new-40000000-0000-0000-0000-000000000001" in instructions.text
    )
    assert "do not download or run the" in instructions.text
    assert "local AgentPost bootstrap" in instructions.text
    assert "Do not ask the Human for a server URL, API key, Bearer token" in instructions.text
    assert reconnect.status_code == 200
    assert (
        "mcp_url=https://agentpost.example/mcp/connect/"
        "agent-5a7044c7-6a5e-48e9-90dd-78680c91dcb9" in reconnect.text
    )
    assert "existing_agent_id=5a7044c7-6a5e-48e9-90dd-78680c91dcb9" in reconnect.text
    assert "macOS, Linux, and Windows" in instructions.text


def test_manus_connection_contract_uses_new_local_folder_task(
    settings: Settings,
    database: Database,
) -> None:
    staged = Settings(
        environment="test",
        database_url=settings.database_url,
        storage_path=settings.storage_path,
        manus_setup_platforms="mac,windows",
        connector_release_version="0.1.17",
        connector_wheel_url="https://agentpost.me/downloads/agentpost-0.1.17-py3-none-any.whl",
        connector_wheel_sha256="a" * 64,
        public_base_url="https://agentpost.me",
        log_level="WARNING",
    )
    with _control_client(staged, database) as local_client:
        instructions = local_client.get("/connect/manus?new=40000000-0000-0000-0000-000000000001")

    assert instructions.status_code == 200
    assert "target_host=manus" in instructions.text
    assert "setup manus --new-agent-intent" in instructions.text
    assert "dedicated local folder" in instructions.text
    assert "status=local_folder_ready and host=manus" in instructions.text
    assert "create a new Manus task" in instructions.text
    assert "./xingyunyi request-stdin" in instructions.text
    assert "manus_local_folder_adapter_confirmed" in instructions.text
    assert "MCP tools/list is unconfirmed" in instructions.text
    assert "Do not use Custom MCP, Remote MCP" in instructions.text


def test_doubao_work_connection_contract_uses_desktop_custom_mcp_and_fails_closed(
    client: TestClient,
    settings: Settings,
    database: Database,
) -> None:
    unavailable = client.get("/connect/doubao_work?new=40000000-0000-0000-0000-000000000001")
    assert unavailable.status_code == 409
    assert "doubao_work_remote_mcp_not_released" in unavailable.text
    assert "API key" in unavailable.text

    staged = Settings(
        environment="test",
        database_url=settings.database_url,
        storage_path=settings.storage_path,
        remote_mcp_oauth_enabled=True,
        doubao_work_remote_mcp_enabled=True,
        public_base_url="https://agentpost.example",
        remote_mcp_resource_url="https://agentpost.example/mcp",
        log_level="WARNING",
    )
    with _control_client(staged, database) as remote_client:
        instructions = remote_client.get(
            "/connect/doubao_work?new=40000000-0000-0000-0000-000000000001"
        )
        reconnect = remote_client.get(
            "/connect/doubao_work?agent=5a7044c7-6a5e-48e9-90dd-78680c91dcb9"
        )

    assert instructions.status_code == 200
    assert instructions.headers["X-AgentPost-Connection-Code"] == "AP-DOUBAO-WORK-V1"
    assert "target_host=doubao_work" in instructions.text
    assert "target_name=豆包工作" in instructions.text
    assert "connection_mode=remote_mcp_oauth" in instructions.text
    assert "mcp_url=https://agentpost.example/mcp" in instructions.text
    assert "desktop client's built-in 自定义连接器" in instructions.text
    assert "choose HTTP transport" in instructions.text
    assert "Do not add a\nHeader" in instructions.text
    assert "browser and mobile clients do not provide" in instructions.text
    assert "doubao_work_custom_mcp_oauth_unavailable" in instructions.text
    assert reconnect.status_code == 200
    assert "existing_agent_id=5a7044c7-6a5e-48e9-90dd-78680c91dcb9" in reconnect.text


def test_doubao_work_connection_contract_prefers_verified_local_stdio(
    settings: Settings,
    database: Database,
) -> None:
    staged = Settings(
        environment="test",
        database_url=settings.database_url,
        storage_path=settings.storage_path,
        doubao_work_setup_platforms="mac,windows",
        manus_setup_platforms="mac,windows",
        connector_release_version="0.1.17",
        connector_wheel_url=("https://agentpost.me/downloads/agentpost-0.1.17-py3-none-any.whl"),
        connector_wheel_sha256="a" * 64,
        public_base_url="https://agentpost.me",
        log_level="WARNING",
    )
    with _control_client(staged, database) as local_client:
        instructions = local_client.get(
            "/connect/doubao_work?new=40000000-0000-0000-0000-000000000001"
        )

    assert instructions.status_code == 200
    assert "target_host=doubao_work" in instructions.text
    assert "setup doubao_work --new-agent-intent" in instructions.text
    assert "新建自定义连接器" in instructions.text
    assert "status=native_registration_required" in instructions.text
    assert "leave args and env empty" in instructions.text
    assert "Remote MCP gate" in instructions.text


def test_auth_config_exposes_release_platforms_per_host(
    settings: Settings,
    database: Database,
) -> None:
    staged = Settings(
        environment="test",
        database_url=settings.database_url,
        storage_path=settings.storage_path,
        api_key_pepper="test-agent-pepper",
        codex_setup_platforms="mac,linux,windows",
        workbuddy_setup_platforms="mac,linux,windows",
        doubao_work_setup_platforms="mac,linux,windows",
        manus_setup_platforms="mac,linux,windows",
        openclaw_setup_platforms="mac,linux,windows",
        hermes_setup_platforms="mac,linux,windows",
        connector_release_version="0.1.1",
        connector_wheel_url=("https://agentpost.me/downloads/agentpost-0.1.1-py3-none-any.whl"),
        connector_wheel_sha256="a" * 64,
        log_level="WARNING",
    )
    with _control_client(staged, database) as client:
        response = client.get("/api/v1/auth/config")

    assert response.status_code == 200
    assert response.json()["codex_setup_platforms"] == ["mac", "linux", "windows"]
    assert response.json()["host_setup_platforms"] == {
        host: ["mac", "linux", "windows"]
        for host in (
            "codex",
            "workbuddy",
            "doubao_work",
            "manus",
            "openclaw",
            "hermes",
        )
    }
    assert response.json()["host_connection_modes"] == {
        "workbuddy": "local_bootstrap",
        "doubao_work": "local_bootstrap",
        "openclaw": "local_bootstrap",
        "hermes": "local_bootstrap",
        "codex": "local_bootstrap",
        "manus": "local_bootstrap",
    }
    assert response.json()["connector_release"] == {
        "version": "0.1.1",
        "wheel_url": "https://agentpost.me/downloads/agentpost-0.1.1-py3-none-any.whl",
        "wheel_sha256": "a" * 64,
    }
    assert response.json()["protocol_contract_version"] == "0.1"


def test_human_identity_uses_a_separate_one_time_key_and_admin_boundary(
    settings: Settings,
    database: Database,
) -> None:
    with _control_client(settings, database) as client:
        hidden = client.post(
            "/api/v1/admin/humans",
            headers={"Authorization": "Bearer wrong"},
            json={"email": "owner@example.com", "display_name": "Owner"},
        )
        created = _create_human(client, "Owner@Example.com", "  北辰  ")
        key = created["access_key"]
        agent_key = _create_agent(client, "alice@agents.local", "Alice")["api_key"]

        human_me = client.get(
            "/api/v1/orbit/me",
            headers={"Authorization": f"Bearer {key}"},
        )
        agent_as_human = client.get(
            "/api/v1/orbit/me",
            headers={"Authorization": f"Bearer {agent_key}"},
        )
        duplicate = client.post(
            "/api/v1/admin/humans",
            headers=_admin_headers(),
            json={"email": "owner@example.com", "display_name": "Other"},
        )
        listed = client.get("/api/v1/admin/humans", headers=_admin_headers())

    assert hidden.status_code == 404
    assert created["user"]["email"] == "owner@example.com"
    assert created["user"]["display_name"] == "北辰"
    assert isinstance(key, str) and key.startswith("hum_")
    assert not str(agent_key).startswith("hum_")
    assert human_me.status_code == 200
    assert agent_as_human.status_code == 401
    assert agent_as_human.json()["error"]["code"] == "INVALID_HUMAN_ACCESS_KEY"
    assert duplicate.status_code == 409
    assert listed.status_code == 200
    assert listed.json()["items"][0]["email"] == "owner@example.com"
    assert key not in listed.text
    assert "key_digest" not in listed.text

    with database.session_factory() as session:
        user = session.scalar(select(HumanUser).where(HumanUser.email == "owner@example.com"))
        stored_key = session.scalar(select(HumanAccessKey))
        assert user is not None and stored_key is not None
        assert stored_key.key_digest != key
        assert key not in stored_key.key_digest


def test_human_owner_can_rename_handle_without_changing_durable_agent_state(
    settings: Settings,
    database: Database,
) -> None:
    with _control_client(settings, database) as client:
        sender = _create_agent(client, "sender@agents.local", "Sender")
        target = _create_agent(client, "stable-target@agents.local", "Research Codex")
        owner = _create_human(client, "owner@example.com", "张子良")
        _grant(
            client,
            human_id=owner["user"]["id"],
            agent_id=target["agent"]["id"],
            role="owner",
        )
        sent = client.post(
            "/api/v1/messages",
            headers={
                "Authorization": f"Bearer {sender['api_key']}",
                "Idempotency-Key": "handle-history-invariant",
            },
            json={
                "to": [{"address": target["agent"]["address"]}],
                "type": "message",
                "subject": "历史消息",
                "content": {"format": "text", "body": "必须保留"},
            },
        )
        assert sent.status_code == 201, sent.text

        with database.session_factory() as session:
            target_id = UUID(str(target["agent"]["id"]))
            owner_id = UUID(str(owner["user"]["id"]))
            connector = ConnectorInstance(
                connector_id="con_handle_invariant",
                agent_id=target_id,
                human_user_id=owner_id,
                connector_type="codex",
                display_name="Codex on Mars Mac",
                status="active",
                health_status="healthy",
            )
            session.add(connector)
            session.flush()
            binding = AgentConnectorBinding(
                agent_id=target_id,
                connector_instance_id=connector.id,
            )
            rule = AccessRule(
                owner_agent_id=target_id,
                effect="allow",
                subject_type="agent",
                subject=sender["agent"]["address"],
            )
            session.add_all([binding, rule])
            session.commit()
            durable_before = {
                "agent_id": target["agent"]["id"],
                "address": target["agent"]["address"],
                "message_id": sent.json()["message_id"],
                "thread_id": sent.json()["thread_id"],
                "delivery_id": sent.json()["delivery"]["delivery_id"],
                "rule_id": rule.id,
                "connector_id": connector.id,
                "binding_connector_id": binding.connector_instance_id,
            }

        human_headers = {"Authorization": f"Bearer {owner['access_key']}"}
        first = client.patch(
            f"/api/v1/orbit/agents/{target['agent']['id']}/handle",
            headers=human_headers,
            json={"handle": "  KCode  "},
        )
        second = client.patch(
            f"/api/v1/orbit/agents/{target['agent']['id']}/handle",
            headers=human_headers,
            json={"handle": "ziliang-codex"},
        )
        dashboard = client.get("/api/v1/orbit/dashboard", headers=human_headers)

    assert first.status_code == second.status_code == dashboard.status_code == 200
    assert first.json()["handle"] == "kcode"
    assert second.json()["handle"] == "ziliang-codex"
    assert second.json()["id"] == durable_before["agent_id"]
    assert second.json()["address"] == durable_before["address"]
    assert dashboard.json()["agents"][0]["handle"] == "ziliang-codex"

    with database.session_factory() as session:
        agent = session.get(Agent, UUID(str(target["agent"]["id"])))
        message = session.get(Message, durable_before["message_id"])
        delivery = session.scalar(
            select(Delivery).where(Delivery.message_id == durable_before["message_id"])
        )
        rule = session.get(AccessRule, durable_before["rule_id"])
        binding = session.get(AgentConnectorBinding, UUID(str(target["agent"]["id"])))
        connector = session.get(ConnectorInstance, durable_before["connector_id"])
        audits = list(
            session.scalars(
                select(HumanActionAudit).where(
                    HumanActionAudit.action == "control.agent_handle_updated"
                )
            )
        )
        assert agent is not None and agent.handle == "ziliang-codex"
        assert agent.address == durable_before["address"]
        assert message is not None and str(message.thread_id) == durable_before["thread_id"]
        assert delivery is not None and str(delivery.id) == durable_before["delivery_id"]
        assert rule is not None and rule.id == durable_before["rule_id"]
        assert binding is not None
        assert binding.connector_instance_id == durable_before["binding_connector_id"]
        assert connector is not None and connector.id == durable_before["connector_id"]
        assert len(audits) == 2


def test_non_owner_cannot_change_agent_handle(
    settings: Settings,
    database: Database,
) -> None:
    with _control_client(settings, database) as client:
        target = _create_agent(client, "target@agents.local", "Target")
        viewer = _create_human(client, "viewer@example.com", "Viewer")
        _grant(
            client,
            human_id=viewer["user"]["id"],
            agent_id=target["agent"]["id"],
            role="viewer",
        )

        denied = client.patch(
            f"/api/v1/orbit/agents/{target['agent']['id']}/handle",
            headers={"Authorization": f"Bearer {viewer['access_key']}"},
            json={"handle": "stolen-name"},
        )

    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "AGENT_HANDLE_ACCESS_DENIED"


def test_owner_can_choose_the_default_agent_used_for_human_name_contact(
    settings: Settings,
    database: Database,
) -> None:
    with _control_client(settings, database) as client:
        first = _create_agent(client, "first-default@agents.local", "First Codex")
        second = _create_agent(client, "second-default@agents.local", "Second WorkBuddy")
        owner = _create_human(client, "default-owner@example.com", "默认联系人")
        _grant(
            client,
            human_id=owner["user"]["id"],
            agent_id=first["agent"]["id"],
            role="owner",
        )
        _grant(
            client,
            human_id=owner["user"]["id"],
            agent_id=second["agent"]["id"],
            role="owner",
        )
        headers = {"Authorization": f"Bearer {owner['access_key']}"}

        before = client.get("/api/v1/orbit/dashboard", headers=headers)
        updated = client.put(
            f"/api/v1/orbit/agents/{second['agent']['id']}/default",
            headers=headers,
        )
        after = client.get("/api/v1/orbit/dashboard", headers=headers)
        deleted = client.request(
            "DELETE",
            f"/api/v1/orbit/agents/{second['agent']['id']}",
            headers=headers,
            json={"confirmation": "delete"},
        )
        fallback = client.get("/api/v1/orbit/dashboard", headers=headers)

    assert (
        before.status_code
        == updated.status_code
        == after.status_code
        == fallback.status_code
        == 200
    )
    assert deleted.status_code == 204
    assert before.json()["user"]["default_agent_id"] == first["agent"]["id"]
    assert updated.json()["default_agent_id"] == second["agent"]["id"]
    default_agents = [agent for agent in after.json()["agents"] if agent["is_default"]]
    assert [agent["id"] for agent in default_agents] == [second["agent"]["id"]]
    assert fallback.json()["user"]["default_agent_id"] == first["agent"]["id"]

    with database.session_factory() as session:
        audit = session.scalar(
            select(HumanActionAudit).where(
                HumanActionAudit.action == "control.default_agent_updated"
            )
        )
        assert audit is not None
        assert audit.target_id == second["agent"]["id"]


def test_owner_dashboard_separates_delivery_from_work_and_isolates_other_agents(
    settings: Settings,
    database: Database,
) -> None:
    with _control_client(settings, database) as client:
        alice = _create_agent(client, "alice@agents.local", "Alice")
        bob = _create_agent(client, "bob@agents.local", "Bob")
        carol = _create_agent(client, "carol@agents.local", "Carol")
        owner = _create_human(client, "owner@example.com", "北辰")
        outsider = _create_human(client, "outsider@example.com", "外部观察者")
        _grant(
            client,
            human_id=owner["user"]["id"],
            agent_id=alice["agent"]["id"],
            role="owner",
        )
        _grant(
            client,
            human_id=outsider["user"]["id"],
            agent_id=carol["agent"]["id"],
            role="owner",
        )

        task = client.post(
            "/api/v1/messages",
            headers={
                "Authorization": f"Bearer {alice['api_key']}",
                "Idempotency-Key": "orbit-owner-task",
            },
            json={
                "to": [{"address": "bob@agents.local"}],
                "type": "task",
                "subject": "分析本周银行市场",
                "content": {"format": "text", "body": "请形成风险提示"},
                "task": {"instruction": "请形成风险提示"},
                "priority": "high",
            },
        )
        assert task.status_code == 201
        unrelated = client.post(
            "/api/v1/messages",
            headers={
                "Authorization": f"Bearer {carol['api_key']}",
                "Idempotency-Key": "orbit-private-message",
            },
            json={
                "to": [{"address": "bob@agents.local"}],
                "type": "message",
                "subject": "另一位用户的私密通信",
                "content": {"format": "text", "body": "never-visible-owner-secret"},
            },
        )
        assert unrelated.status_code == 201

        bob_ack = client.post(
            f"/api/v1/messages/{task.json()['message_id']}/ack",
            headers={"Authorization": f"Bearer {bob['api_key']}"},
        )
        assert bob_ack.status_code == 200
        owner_headers = {"Authorization": f"Bearer {owner['access_key']}"}
        before_result = client.get("/api/v1/orbit/dashboard", headers=owner_headers)

        result = client.post(
            f"/api/v1/messages/{task.json()['message_id']}/reply",
            headers={
                "Authorization": f"Bearer {bob['api_key']}",
                "Idempotency-Key": "orbit-owner-task-result",
            },
            json={
                "type": "result",
                "subject": "银行市场分析完成",
                "content": {"format": "text", "body": "结论已形成"},
                "result": {"status": "completed", "summary": "已形成三项风险提示"},
            },
        )
        assert result.status_code == 201
        after_result = client.get("/api/v1/orbit/dashboard", headers=owner_headers)

    assert before_result.status_code == after_result.status_code == 200
    before = before_result.json()
    assert before["product"] == "星云驿"
    assert before["surface"] == "星轨"
    assert before["data_plane"] == "云驿"
    assert before["metrics"]["agent_count"] == 1
    assert before["agents"][0]["address"] == "alice@agents.local"
    assert before["agents"][0]["role"] == "owner"
    assert before["tasks"][0]["communication_state"] == "acked"
    assert before["tasks"][0]["work_state"] == "pending"
    assert before["metrics"]["pending_task_count"] == 1
    rendered_before = before_result.text
    assert "请形成风险提示" in rendered_before
    assert "never-visible-owner-secret" not in rendered_before
    assert "另一位用户的私密通信" not in rendered_before

    after = after_result.json()
    assert after["tasks"][0]["work_state"] == "completed"
    assert after["tasks"][0]["result_message_id"] == result.json()["message_id"]
    assert after["tasks"][0]["result_summary"] == "已形成三项风险提示"
    assert after["metrics"]["pending_task_count"] == 0


def test_each_task_round_is_completed_by_a_direct_reply(
    settings: Settings,
    database: Database,
) -> None:
    with _control_client(settings, database) as client:
        alice = _create_agent(client, "round-owner@agents.local", "Round owner")
        bob = _create_agent(client, "round-worker@agents.local", "Round worker")
        owner = _create_human(client, "rounds@example.com", "多轮任务用户")
        _grant(
            client,
            human_id=owner["user"]["id"],
            agent_id=alice["agent"]["id"],
            role="owner",
        )

        task_ids: list[str] = []
        thread_id = None
        reply_parent_id = None
        for round_number in range(1, 4):
            task_payload: dict[str, object] = {
                "type": "task",
                "subject": f"第 {round_number} 轮任务",
                "content": {"format": "text", "body": f"请处理第 {round_number} 轮"},
                "task": {"instruction": f"请处理第 {round_number} 轮"},
            }
            if reply_parent_id is None:
                task_payload["to"] = [{"address": bob["agent"]["address"]}]
                task = client.post(
                    "/api/v1/messages",
                    headers={
                        "Authorization": f"Bearer {alice['api_key']}",
                        "Idempotency-Key": f"orbit-task-round-{round_number}",
                    },
                    json=task_payload,
                )
            else:
                task = client.post(
                    f"/api/v1/messages/{reply_parent_id}/reply",
                    headers={
                        "Authorization": f"Bearer {alice['api_key']}",
                        "Idempotency-Key": f"orbit-task-round-{round_number}",
                    },
                    json=task_payload,
                )
            assert task.status_code == 201, task.text
            thread_id = task.json()["thread_id"]
            task_ids.append(task.json()["message_id"])
            if round_number < 3:
                reply = client.post(
                    f"/api/v1/messages/{task.json()['message_id']}/reply",
                    headers={
                        "Authorization": f"Bearer {bob['api_key']}",
                        "Idempotency-Key": f"orbit-task-round-reply-{round_number}",
                    },
                    json={
                        "type": "response",
                        "subject": f"第 {round_number} 轮回复",
                        "content": {"format": "text", "body": "这一轮已经处理并回复"},
                    },
                )
                assert reply.status_code == 201, reply.text
                reply_parent_id = reply.json()["message_id"]

        headers = {"Authorization": f"Bearer {owner['access_key']}"}
        dashboard = client.get("/api/v1/orbit/dashboard", headers=headers)
        threads = client.get("/api/v1/orbit/threads", headers=headers)
        detail = client.get(f"/api/v1/orbit/threads/{thread_id}", headers=headers)

    assert dashboard.status_code == threads.status_code == detail.status_code == 200
    tasks_by_id = {task["task_message_id"]: task for task in dashboard.json()["tasks"]}
    assert tasks_by_id[task_ids[0]]["work_state"] == "completed"
    assert tasks_by_id[task_ids[1]]["work_state"] == "completed"
    assert tasks_by_id[task_ids[2]]["work_state"] == "pending"
    assert dashboard.json()["metrics"]["pending_task_count"] == 1
    thread = next(item for item in threads.json() if item["thread_id"] == thread_id)
    assert thread["pending_task_count"] == 1
    detail_tasks = {
        message["message_id"]: message["work_state"]
        for message in detail.json()["messages"]
        if message["message_type"] == "task"
    }
    assert detail_tasks == {
        task_ids[0]: "completed",
        task_ids[1]: "completed",
        task_ids[2]: "pending",
    }


def test_auditor_content_is_redacted_and_revocation_removes_all_visibility(
    settings: Settings,
    database: Database,
) -> None:
    with _control_client(settings, database) as client:
        alice = _create_agent(client, "alice@agents.local", "Alice")
        _create_agent(client, "bob@agents.local", "Bob")
        auditor = _create_human(client, "audit@example.com", "审计员")
        _grant(
            client,
            human_id=auditor["user"]["id"],
            agent_id=alice["agent"]["id"],
            role="auditor",
        )
        sent = client.post(
            "/api/v1/messages",
            headers={
                "Authorization": f"Bearer {alice['api_key']}",
                "Idempotency-Key": "orbit-audit-redaction",
            },
            json={
                "to": [{"address": "bob@agents.local"}],
                "type": "message",
                "subject": "审计可见主题",
                "content": {"format": "text", "body": "sensitive-body-canary"},
            },
        )
        assert sent.status_code == 201
        headers = {"Authorization": f"Bearer {auditor['access_key']}"}
        visible = client.get("/api/v1/orbit/messages", headers=headers)
        thread_detail = client.get(
            f"/api/v1/orbit/threads/{sent.json()['thread_id']}",
            headers=headers,
        )
        body_search = client.get(
            "/api/v1/orbit/threads",
            params={"query": "sensitive-body-canary"},
            headers=headers,
        )
        revoked = client.delete(
            f"/api/v1/admin/humans/{auditor['user']['id']}/agents/{alice['agent']['id']}",
            headers=_admin_headers(),
        )
        after = client.get("/api/v1/orbit/dashboard", headers=headers)

    assert visible.status_code == 200
    assert visible.json()[0]["subject"] == "审计可见主题"
    assert visible.json()[0]["content_body"] is None
    assert visible.json()[0]["content_redacted"] is True
    assert "sensitive-body-canary" not in visible.text
    assert thread_detail.status_code == 200
    assert thread_detail.json()["messages"][0]["content_body"] is None
    assert thread_detail.json()["messages"][0]["content_redacted"] is True
    assert "sensitive-body-canary" not in thread_detail.text
    assert body_search.status_code == 200
    assert body_search.json() == []
    assert revoked.status_code == 204
    assert after.status_code == 200
    assert after.json()["metrics"]["agent_count"] == 0
    assert after.json()["recent_messages"] == []


def test_human_threads_keep_topics_separate_search_authorized_content_and_do_not_mark_read(
    settings: Settings,
    database: Database,
) -> None:
    with _control_client(settings, database) as client:
        alice = _create_agent(client, "alice@agents.local", "Alice")
        bob = _create_agent(client, "bob@agents.local", "Bob")
        human = _create_human(client, "threads@example.com", "对话观察者")
        recipient_owner = _create_human(client, "recipient@example.com", "收件人用户")
        outsider = _create_human(client, "thread-outsider@example.com", "无权用户")
        _grant(
            client,
            human_id=human["user"]["id"],
            agent_id=alice["agent"]["id"],
            role="owner",
        )
        _grant(
            client,
            human_id=recipient_owner["user"]["id"],
            agent_id=bob["agent"]["id"],
            role="owner",
        )
        first = client.post(
            "/api/v1/messages",
            headers={
                "Authorization": f"Bearer {alice['api_key']}",
                "Idempotency-Key": "orbit-human-thread-one",
            },
            json={
                "to": [{"address": bob["agent"]["address"]}],
                "type": "message",
                "subject": "供应链风险",
                "content": {"format": "text", "body": "first-thread-body"},
            },
        )
        second = client.post(
            "/api/v1/messages",
            headers={
                "Authorization": f"Bearer {alice['api_key']}",
                "Idempotency-Key": "orbit-human-thread-two",
            },
            json={
                "to": [{"address": bob["agent"]["address"]}],
                "type": "message",
                "subject": "市场周报",
                "content": {"format": "text", "body": "separate-thread-body"},
            },
        )
        assert first.status_code == second.status_code == 201
        reply = client.post(
            f"/api/v1/messages/{first.json()['message_id']}/reply",
            headers={
                "Authorization": f"Bearer {bob['api_key']}",
                "Idempotency-Key": "orbit-human-thread-reply",
            },
            json={
                "type": "response",
                "subject": "供应链风险回复",
                "content": {"format": "text", "body": "authorized-reply-canary"},
            },
        )
        assert reply.status_code == 201
        with database.session_factory() as session:
            delivery_before = session.scalar(
                select(Delivery).where(Delivery.message_id == first.json()["message_id"])
            )
            assert delivery_before is not None
            state_before = (
                delivery_before.delivery_status,
                delivery_before.read_at,
                delivery_before.acked_at,
            )

        headers = {"Authorization": f"Bearer {human['access_key']}"}
        threads = client.get("/api/v1/orbit/threads", headers=headers)
        detail = client.get(
            f"/api/v1/orbit/threads/{first.json()['thread_id']}",
            headers=headers,
        )
        search = client.get(
            "/api/v1/orbit/threads",
            params={"query": "authorized-reply-canary"},
            headers=headers,
        )
        related = client.get(
            "/api/v1/orbit/threads",
            params={"agent_id": alice["agent"]["id"]},
            headers=headers,
        )
        hidden_related = client.get(
            "/api/v1/orbit/threads",
            params={"agent_id": bob["agent"]["id"]},
            headers=headers,
        )
        outsider_headers = {"Authorization": f"Bearer {outsider['access_key']}"}
        hidden = client.get(
            f"/api/v1/orbit/threads/{first.json()['thread_id']}",
            headers=outsider_headers,
        )
        with database.session_factory() as session:
            delivery_after = session.scalar(
                select(Delivery).where(Delivery.message_id == first.json()["message_id"])
            )
            assert delivery_after is not None
            state_after = (
                delivery_after.delivery_status,
                delivery_after.read_at,
                delivery_after.acked_at,
            )

    assert threads.status_code == detail.status_code == search.status_code == 200
    assert related.status_code == hidden_related.status_code == 200
    assert {item["topic"] for item in threads.json()} == {"供应链风险", "市场周报"}
    first_summary = next(
        item for item in threads.json() if item["thread_id"] == first.json()["thread_id"]
    )
    assert first_summary["message_count"] == 2
    assert first_summary["human_view_state"] == "unread"
    assert first_summary["human_viewed_at"] is None
    assert first_summary["latest_sender"]["display_name"] == "Bob"
    assert first_summary["latest_recipient"]["display_name"] == "Alice"
    assert first_summary["conversation_state"] == "waiting_for_me"
    assert {participant["display_name"] for participant in first_summary["participants"]} == {
        "Alice",
        "Bob",
    }
    participants = {
        participant["display_name"]: participant for participant in first_summary["participants"]
    }
    assert participants["Alice"]["owner_display_name"] == "对话观察者"
    assert participants["Alice"]["owned_by_current_human"] is True
    assert participants["Bob"]["owner_display_name"] == "收件人用户"
    assert participants["Bob"]["owned_by_current_human"] is False
    assert [message["reply_to"] for message in detail.json()["messages"]] == [
        None,
        first.json()["message_id"],
    ]
    assert detail.json()["messages"][1]["content_body"] == "authorized-reply-canary"
    assert len(search.json()) == 1
    assert search.json()[0]["thread_id"] == first.json()["thread_id"]
    assert len(related.json()) == 2
    assert hidden_related.json() == []
    assert hidden.status_code == 404
    assert state_after == state_before

    with _control_client(settings, database) as client:
        headers = {"Authorization": f"Bearer {human['access_key']}"}
        viewed = client.post(
            f"/api/v1/orbit/threads/{first.json()['thread_id']}/viewed",
            headers=headers,
        )
        after_view = client.get("/api/v1/orbit/threads", headers=headers)
        denied_view = client.post(
            f"/api/v1/orbit/threads/{first.json()['thread_id']}/viewed",
            headers={"Authorization": f"Bearer {outsider['access_key']}"},
        )
        assert viewed.status_code == 200
        assert viewed.json()["human_view_state"] == "viewed"
        viewed_summary = next(
            item for item in after_view.json() if item["thread_id"] == first.json()["thread_id"]
        )
        assert viewed_summary["human_view_state"] == "viewed"
        assert viewed_summary["human_viewed_at"] is not None
        assert denied_view.status_code == 404

        new_reply = client.post(
            f"/api/v1/messages/{reply.json()['message_id']}/reply",
            headers={
                "Authorization": f"Bearer {alice['api_key']}",
                "Idempotency-Key": "orbit-human-thread-new-after-view",
            },
            json={
                "type": "response",
                "subject": "供应链风险再次回复",
                "content": {"format": "text", "body": "new-after-human-view"},
            },
        )
        assert new_reply.status_code == 201
        unread_again = client.get("/api/v1/orbit/threads", headers=headers)
        refreshed_summary = next(
            item for item in unread_again.json() if item["thread_id"] == first.json()["thread_id"]
        )
        assert refreshed_summary["human_view_state"] == "unread"

    with database.session_factory() as session:
        stored_view = session.get(
            HumanThreadView,
            (UUID(human["user"]["id"]), UUID(first.json()["thread_id"])),
        )
        assert stored_view is not None
        assert stored_view.viewed_through_message_id == reply.json()["message_id"]


def test_human_attachment_open_and_html_preview_are_authorized_and_read_only(
    settings: Settings,
    database: Database,
) -> None:
    with _control_client(settings, database) as client:
        alice = _create_agent(client, "alice-files@agents.local", "Alice Files")
        bob = _create_agent(client, "bob-files@agents.local", "Bob Files")
        owner = _create_human(client, "file-owner@example.com", "文件所有者")
        auditor = _create_human(client, "file-auditor@example.com", "文件审计员")
        outsider = _create_human(client, "file-outsider@example.com", "无权用户")
        _grant(
            client,
            human_id=owner["user"]["id"],
            agent_id=alice["agent"]["id"],
            role="owner",
        )
        _grant(
            client,
            human_id=auditor["user"]["id"],
            agent_id=alice["agent"]["id"],
            role="auditor",
        )

        pdf_bytes = b"%PDF-1.4\n% AgentPost preview test\n"
        html_bytes = (
            b"<!doctype html><meta charset=utf-8><h1>Safe preview</h1>"
            b"<script>parent.document.body.dataset.unsafe='true'</script>"
        )
        pdf_upload = client.post(
            "/api/v1/attachments",
            headers={"Authorization": f"Bearer {alice['api_key']}"},
            files={"file": ("report.pdf", pdf_bytes, "application/pdf")},
        )
        html_upload = client.post(
            "/api/v1/attachments",
            headers={"Authorization": f"Bearer {alice['api_key']}"},
            files={"file": ("preview.html", html_bytes, "text/html")},
        )
        assert pdf_upload.status_code == html_upload.status_code == 201
        sent = client.post(
            "/api/v1/messages",
            headers={
                "Authorization": f"Bearer {alice['api_key']}",
                "Idempotency-Key": "orbit-human-safe-attachment-preview",
            },
            json={
                "to": [{"address": bob["agent"]["address"]}],
                "type": "message",
                "subject": "附件查看",
                "content": {"format": "text", "body": "请查看附件"},
                "attachments": [pdf_upload.json()["id"], html_upload.json()["id"]],
            },
        )
        assert sent.status_code == 201
        with database.session_factory() as session:
            delivery_before = session.scalar(
                select(Delivery).where(Delivery.message_id == sent.json()["message_id"])
            )
            assert delivery_before is not None
            state_before = (
                delivery_before.delivery_status,
                delivery_before.read_at,
                delivery_before.acked_at,
            )

        owner_headers = {"Authorization": f"Bearer {owner['access_key']}"}
        pdf_download = client.get(
            f"/api/v1/orbit/attachments/{pdf_upload.json()['id']}",
            headers=owner_headers,
        )
        pdf_preview = client.get(
            f"/api/v1/orbit/attachments/{pdf_upload.json()['id']}/preview",
            headers=owner_headers,
        )
        html_preview = client.get(
            f"/api/v1/orbit/attachments/{html_upload.json()['id']}/preview",
            headers=owner_headers,
        )
        auditor_preview = client.get(
            f"/api/v1/orbit/attachments/{html_upload.json()['id']}/preview",
            headers={"Authorization": f"Bearer {auditor['access_key']}"},
        )
        outsider_preview = client.get(
            f"/api/v1/orbit/attachments/{html_upload.json()['id']}/preview",
            headers={"Authorization": f"Bearer {outsider['access_key']}"},
        )
        with database.session_factory() as session:
            delivery_after = session.scalar(
                select(Delivery).where(Delivery.message_id == sent.json()["message_id"])
            )
            assert delivery_after is not None
            state_after = (
                delivery_after.delivery_status,
                delivery_after.read_at,
                delivery_after.acked_at,
            )

    assert pdf_download.status_code == 200
    assert pdf_download.content == pdf_bytes
    assert pdf_download.headers["content-type"] == "application/octet-stream"
    assert pdf_download.headers["content-disposition"].startswith("attachment;")
    assert pdf_download.headers["cache-control"] == "no-store"
    assert pdf_preview.status_code == 200
    assert pdf_preview.content == pdf_bytes
    assert pdf_preview.headers["content-type"] == "application/pdf"
    assert pdf_preview.headers["content-disposition"].startswith("inline;")
    assert "sandbox" in pdf_preview.headers["content-security-policy"]
    assert html_preview.status_code == 200
    assert html_preview.content == html_bytes
    assert html_preview.headers["content-type"].startswith("text/html")
    assert "default-src 'none'" in html_preview.headers["content-security-policy"]
    assert "form-action 'none'" in html_preview.headers["content-security-policy"]
    assert auditor_preview.status_code == outsider_preview.status_code == 404
    assert state_after == state_before


def test_agent_connection_projection_uses_current_binding_heartbeat_and_error_evidence(
    settings: Settings,
    database: Database,
) -> None:
    with _control_client(settings, database) as client:
        human = _create_human(client, "connection-viewer@example.com", "连接观察者")
        agents = {
            state: _create_agent(client, f"{state}@agents.local", state)
            for state in ["connected", "awaiting", "offline", "broken", "disconnected"]
        }
        for agent in agents.values():
            _grant(
                client,
                human_id=human["user"]["id"],
                agent_id=agent["agent"]["id"],
                role="viewer",
            )
        with database.session_factory() as session:
            now = datetime.now(UTC)
            connector_specs = {
                "connected": {"health_status": "healthy", "last_heartbeat_at": now},
                "awaiting": {"health_status": "unknown", "last_heartbeat_at": None},
                "offline": {
                    "health_status": "healthy",
                    "last_heartbeat_at": now - timedelta(minutes=6),
                },
                "broken": {
                    "health_status": "error",
                    "last_heartbeat_at": now,
                    "last_error_code": "demo_connection_error",
                },
            }
            for name, connector_values in connector_specs.items():
                agent_id = UUID(str(agents[name]["agent"]["id"]))
                connector = ConnectorInstance(
                    connector_id=f"con_{name}",
                    agent_id=agent_id,
                    human_user_id=UUID(str(human["user"]["id"])),
                    connector_type="codex",
                    display_name=f"{name} connector",
                    status="active",
                    **connector_values,
                )
                session.add(connector)
                session.flush()
                session.add(
                    AgentConnectorBinding(
                        agent_id=agent_id,
                        connector_instance_id=connector.id,
                    )
                )
            session.commit()
        dashboard = client.get(
            "/api/v1/orbit/dashboard",
            headers={"Authorization": f"Bearer {human['access_key']}"},
        )

    assert dashboard.status_code == 200
    projected = {agent["address"].partition("@")[0]: agent for agent in dashboard.json()["agents"]}
    assert {name: agent["connection_state"] for name, agent in projected.items()} == {
        "awaiting": "awaiting_agent",
        "broken": "connection_error",
        "connected": "connected",
        "disconnected": "disconnected",
        "offline": "offline",
    }
    assert projected["connected"]["current_connector_type"] == "codex"
    assert projected["broken"]["current_connector_error_code"] == "demo_connection_error"
    assert dashboard.json()["metrics"]["connected_agent_count"] == 1


def test_human_key_creates_revocable_short_lived_browser_session(
    settings: Settings,
    database: Database,
) -> None:
    with _control_client(settings, database) as client:
        human = _create_human(client, "session@example.com", "会话用户")
        agent = _create_agent(client, "agent@agents.local", "Agent")
        agent_rejected = client.post(
            "/api/v1/orbit/session",
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        login = client.post(
            "/api/v1/orbit/session",
            headers={"Authorization": f"Bearer {human['access_key']}"},
        )
        raw_session = client.cookies.get("xinggui_session")
        dashboard = client.get("/api/v1/orbit/dashboard")

        assert agent_rejected.status_code == 401
        assert login.status_code == 201
        assert login.json()["authentication"] == "browser_session"
        assert login.json()["user"]["email"] == "session@example.com"
        raw_csrf = login.json()["csrf_token"]
        assert isinstance(raw_csrf, str) and raw_csrf.startswith("csrf_")
        assert "access_key" not in login.text
        assert raw_session is not None and raw_session.startswith("hss_")
        cookie_header = login.headers["set-cookie"]
        assert "HttpOnly" in cookie_header
        assert "SameSite=strict" in cookie_header
        assert "Path=/api/v1/orbit" in cookie_header
        assert human["access_key"] not in cookie_header
        assert dashboard.status_code == 200

        with database.session_factory() as db_session:
            stored = db_session.scalar(
                select(HumanSession).where(HumanSession.revoked_at.is_(None))
            )
            assert stored is not None
            assert stored.token_digest != raw_session
            assert raw_session not in stored.token_digest
            assert stored.csrf_token_digest != raw_csrf
            assert raw_csrf not in stored.csrf_token_digest

        denied_logout = client.delete("/api/v1/orbit/session")
        assert denied_logout.status_code == 403
        logout = client.delete(
            "/api/v1/orbit/session",
            headers={"X-CSRF-Token": raw_csrf},
        )
        assert logout.status_code == 204
        client.cookies.set(
            "xinggui_session",
            raw_session,
            path="/api/v1/orbit",
        )
        revoked = client.get("/api/v1/orbit/dashboard")
        assert revoked.status_code == 401
        client.cookies.delete(
            "xinggui_session",
            path="/api/v1/orbit",
        )

        second_login = client.post(
            "/api/v1/orbit/session",
            headers={"Authorization": f"Bearer {human['access_key']}"},
        )
        assert second_login.status_code == 201
        second_raw = client.cookies.get("xinggui_session")
        assert second_raw is not None and second_raw != raw_session

        with database.session_factory() as db_session:
            current = db_session.scalar(
                select(HumanSession).where(HumanSession.revoked_at.is_(None))
            )
            assert current is not None
            current.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            db_session.commit()

        expired = client.get("/api/v1/orbit/dashboard")
        assert expired.status_code == 401
        expired_logout = client.delete("/api/v1/orbit/session")
        assert expired_logout.status_code == 204
        assert "xinggui_session=" in expired_logout.headers["set-cookie"]


def test_production_session_cookie_is_secure(
    settings: Settings,
    database: Database,
) -> None:
    production = Settings(
        environment="production",
        pairing_enabled=False,
        database_url=settings.database_url,
        storage_path=settings.storage_path,
        api_key_pepper="production-agent-pepper",
        human_api_key_pepper="production-human-pepper",
        cursor_secret="production-cursor-secret",
        rate_limit_secret="production-rate-limit-secret",
        registration_token="registration-secret",
        admin_token=ADMIN_KEY,
        log_level="WARNING",
    )
    with TestClient(create_app(settings=production, database=database)) as client:
        human = _create_human(client, "secure@example.com", "HTTPS 用户")
        login = client.post(
            "/api/v1/orbit/session",
            headers={"Authorization": f"Bearer {human['access_key']}"},
        )

    assert login.status_code == 201
    assert "Secure" in login.headers["set-cookie"]
