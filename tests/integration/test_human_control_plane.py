from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from agentpost.config import Settings
from agentpost.control.models import HumanAccessKey, HumanSession, HumanUser
from agentpost.db import Database
from agentpost.main import create_app

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
        codex_setup_platforms=settings.codex_setup_platforms,
        connector_release_version=settings.connector_release_version,
        connector_wheel_url=settings.connector_wheel_url,
        connector_wheel_sha256=settings.connector_wheel_sha256,
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
    auth_config = client.get("/api/v1/auth/config")

    assert home.status_code == orbit.status_code == 200
    assert "星云驿" in orbit.text
    assert "星轨 · 人类控制面" in orbit.text
    assert "云驿 · Agent 通信网" in orbit.text
    assert orbit.headers["Cache-Control"] == "no-store"
    assert "default-src 'none'" in orbit.headers["Content-Security-Policy"]
    assert orbit.headers["X-Content-Type-Options"] == "nosniff"
    assert script.status_code == stylesheet.status_code == 200
    assert auth_config.status_code == 200
    assert auth_config.json()["managed_agent_domain"] == "agents.local"
    assert auth_config.json()["codex_setup_platforms"] == []
    assert auth_config.json()["connector_release"] == {
        "version": "0.1.0",
        "wheel_url": "https://agentpost.me/downloads/agentpost-0.1.0-py3-none-any.whl",
        "wheel_sha256": "1fc3f42e8c1141ce65481778587544fc9bf441438c852c0332594ab24a75fdf7",
    }
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
    assert "recovery-dialog" in orbit.text
    assert "mfa-dialog" in orbit.text
    assert "你想连接哪个 Agent 工具" in orbit.text
    assert "复制安装命令" in orbit.text
    assert "复制连接命令" in orbit.text
    assert "已经看到配对 ID / 代码？手动输入" in orbit.text
    assert "连接器是运行在你电脑上的安全小程序" in orbit.text
    assert "pairing-address-domain" in orbit.text
    assert "只填写 @ 前面的部分" in orbit.text
    assert 'pattern="[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?"' in orbit.text
    assert 'data-connector-type="codex"' in orbit.text
    assert 'data-connector-type="workbuddy"' in orbit.text
    assert 'data-connector-type="openclaw"' in orbit.text
    assert "navigator.clipboard.writeText" in script.text
    assert "FALLBACK_CONNECTOR_RELEASE" in script.text
    assert "#sha256=" in script.text
    assert "codex_setup_platforms" in script.text
    assert 'const extras = nativeCodexSetup ? "mcp,connector" : "connector"' in script.text
    assert '"setup codex"' in script.text
    assert "canonicalPairingLocalId" in script.text
    assert "pairingPayloadProblem" in script.text
    assert ".split(/[,，]/)" in script.text
    assert "Agent 地址格式不正确" in script.text
    assert "AGENTPOST_API_KEY" not in orbit.text
    assert "agt_" not in orbit.text
    assert "账户安全" in orbit.text
    assert "组织星图" in orbit.text
    assert "organization-list" in orbit.text
    assert "open-organization-create" in orbit.text
    assert "organization-manage-dialog" in orbit.text
    assert '"/api/v1/orbit/organization-invitations/accept"' in script.text
    assert "organization-invitation" in script.text
    assert "history.replaceState" in script.text
    assert "organization-domain-name" in orbit.text
    assert "/domains/" in script.text
    assert "organizationDomainProofs.clear()" in script.text
    assert "TXT 记录" in orbit.text
    assert "Agent 连接" in orbit.text
    assert "pairing-dialog" in orbit.text
    assert "revoke-dialog" in orbit.text
    assert "/api/v1/orbit/pairings/" in script.text
    assert "/api/v1/orbit/connectors" in script.text
    assert "pairing-existing-agent" in orbit.text
    assert "existing_agent_id" in script.text
    assert "只替换当前连接器" in orbit.text
    assert "last_heartbeat_at" in script.text
    assert "长期凭证由本地连接器自动领取" in script.text
    assert 'elements.pairingAccessKey.value = ""' in script.text
    assert 'elements.revokeAccessKey.value = ""' in script.text
    assert ".welcome-shell[hidden]" in stylesheet.text
    assert "max-height: calc(100dvh - 32px)" in stylesheet.text


def test_auth_config_exposes_only_release_enabled_codex_platforms(
    settings: Settings,
    database: Database,
) -> None:
    staged = Settings(
        environment="test",
        database_url=settings.database_url,
        storage_path=settings.storage_path,
        api_key_pepper="test-agent-pepper",
        codex_setup_platforms="mac,linux",
        connector_release_version="0.1.1",
        connector_wheel_url=("https://agentpost.me/downloads/agentpost-0.1.1-py3-none-any.whl"),
        connector_wheel_sha256="a" * 64,
        log_level="WARNING",
    )
    with _control_client(staged, database) as client:
        response = client.get("/api/v1/auth/config")

    assert response.status_code == 200
    assert response.json()["codex_setup_platforms"] == ["mac", "linux"]
    assert response.json()["connector_release"] == {
        "version": "0.1.1",
        "wheel_url": "https://agentpost.me/downloads/agentpost-0.1.1-py3-none-any.whl",
        "wheel_sha256": "a" * 64,
    }


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
    assert revoked.status_code == 204
    assert after.status_code == 200
    assert after.json()["metrics"]["agent_count"] == 0
    assert after.json()["recent_messages"] == []


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
