from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from agentpost.config import Settings
from agentpost.db import Database
from agentpost.main import create_app
from agentpost.messaging.models import AuditLog

ADMIN_KEY = "admin-secret-admin-secret-admin-secret"


def _client(settings: Settings, database: Database) -> TestClient:
    protected = Settings(
        environment="test",
        database_url=settings.database_url,
        storage_path=settings.storage_path,
        api_key_pepper="test-agent-pepper",
        human_api_key_pepper="test-human-pepper",
        cursor_secret="test-cursor-secret",
        registration_token="register-secret",
        admin_token=ADMIN_KEY,
        log_level="WARNING",
    )
    return TestClient(create_app(settings=protected, database=database))


def _admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {ADMIN_KEY}"}


def _create_human(client: TestClient, email: str, name: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/admin/humans",
        headers=_admin_headers(),
        json={"email": email, "display_name": name},
    )
    assert response.status_code == 201
    return response.json()


def _create_agent(client: TestClient, address: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/agents",
        headers={"X-Registration-Token": "register-secret"},
        json={
            "address": address,
            "display_name": address.split("@", maxsplit=1)[0].title(),
            "capabilities": ["document-analysis"],
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_organization(client: TestClient, slug: str = "fipay-research") -> dict[str, object]:
    response = client.post(
        "/api/v1/admin/organizations",
        headers=_admin_headers(),
        json={
            "slug": slug,
            "name": "星海研究院",
            "description": "管理银行研究与文档分析 Agent",
        },
    )
    assert response.status_code == 201
    return response.json()


def _set_member(
    client: TestClient,
    organization_id: str,
    human_id: str,
    role: str,
) -> dict[str, object]:
    response = client.put(
        f"/api/v1/admin/organizations/{organization_id}/members/{human_id}",
        headers=_admin_headers(),
        json={"role": role},
    )
    assert response.status_code == 200
    return response.json()


def _assign_agent(
    client: TestClient,
    organization_id: str,
    agent_id: str,
) -> dict[str, object]:
    response = client.put(
        f"/api/v1/admin/organizations/{organization_id}/agents/{agent_id}",
        headers=_admin_headers(),
    )
    assert response.status_code == 200
    return response.json()


def test_admin_bootstrap_enforces_organization_invariants(
    settings: Settings,
    database: Database,
) -> None:
    with _client(settings, database) as client:
        hidden = client.post(
            "/api/v1/admin/organizations",
            headers={"Authorization": "Bearer wrong"},
            json={"slug": "hidden-org", "name": "Hidden"},
        )
        organization = _create_organization(client, "FiPay-Research")
        duplicate = client.post(
            "/api/v1/admin/organizations",
            headers=_admin_headers(),
            json={"slug": "fipay-research", "name": "Duplicate"},
        )
        human = _create_human(client, "owner@example.com", "组织负责人")
        agent = _create_agent(client, "research@agents.local")
        membership = _set_member(
            client,
            str(organization["id"]),
            str(human["user"]["id"]),
            "owner",
        )
        assignment = _assign_agent(
            client,
            str(organization["id"]),
            str(agent["agent"]["id"]),
        )
        replay = _assign_agent(
            client,
            str(organization["id"]),
            str(agent["agent"]["id"]),
        )
        other = _create_organization(client, "other-org")
        conflicting = client.put(
            f"/api/v1/admin/organizations/{other['id']}/agents/{agent['agent']['id']}",
            headers=_admin_headers(),
        )
        listed = client.get("/api/v1/admin/organizations", headers=_admin_headers())
        members = client.get(
            f"/api/v1/admin/organizations/{organization['id']}/members",
            headers=_admin_headers(),
        )
        agents = client.get(
            f"/api/v1/admin/organizations/{organization['id']}/agents",
            headers=_admin_headers(),
        )

    assert hidden.status_code == 404
    assert organization["slug"] == "fipay-research"
    assert organization["name"] == "星海研究院"
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "ORGANIZATION_SLUG_ALREADY_REGISTERED"
    assert membership["role"] == "owner"
    assert membership["human_email"] == "owner@example.com"
    assert assignment == replay
    assert conflicting.status_code == 409
    assert conflicting.json()["error"]["code"] == "AGENT_ALREADY_ASSIGNED_TO_ORGANIZATION"
    by_slug = {item["slug"]: item for item in listed.json()["items"]}
    assert by_slug["fipay-research"]["member_count"] == 1
    assert by_slug["fipay-research"]["agent_count"] == 1
    assert members.json()["items"][0]["human_email"] == "owner@example.com"
    assert "access_key" not in members.text
    assert agents.json()["items"][0]["agent_address"] == "research@agents.local"
    assert "api_key" not in agents.text

    with database.session_factory() as session:
        actions = set(session.scalars(select(AuditLog.action)).all())
    assert {
        "control.organization_created",
        "control.organization_membership_set",
        "control.organization_agent_assigned",
    } <= actions


def test_organization_membership_scopes_agents_and_redacts_auditors(
    settings: Settings,
    database: Database,
) -> None:
    with _client(settings, database) as client:
        organization = _create_organization(client)
        member = _create_human(client, "member@example.com", "研究成员")
        auditor = _create_human(client, "auditor@example.com", "组织审计员")
        outsider = _create_human(client, "outsider@example.com", "组织外用户")
        alice = _create_agent(client, "alice@agents.local")
        _create_agent(client, "bob@agents.local")
        _set_member(client, str(organization["id"]), str(member["user"]["id"]), "member")
        _set_member(client, str(organization["id"]), str(auditor["user"]["id"]), "auditor")
        _assign_agent(
            client,
            str(organization["id"]),
            str(alice["agent"]["id"]),
        )

        sent = client.post(
            "/api/v1/messages",
            headers={
                "Authorization": f"Bearer {alice['api_key']}",
                "Idempotency-Key": "organization-visible-message",
            },
            json={
                "to": [{"address": "bob@agents.local"}],
                "type": "message",
                "subject": "组织研究进度",
                "content": {"format": "text", "body": "organization-body-canary"},
            },
        )
        assert sent.status_code == 201

        member_dashboard = client.get(
            "/api/v1/orbit/dashboard",
            headers={"Authorization": f"Bearer {member['access_key']}"},
        )
        member_organizations = client.get(
            "/api/v1/orbit/organizations",
            headers={"Authorization": f"Bearer {member['access_key']}"},
        )
        auditor_messages = client.get(
            "/api/v1/orbit/messages",
            headers={"Authorization": f"Bearer {auditor['access_key']}"},
        )
        outsider_dashboard = client.get(
            "/api/v1/orbit/dashboard",
            headers={"Authorization": f"Bearer {outsider['access_key']}"},
        )
        human_cannot_self_join = client.put(
            f"/api/v1/admin/organizations/{organization['id']}/members/{outsider['user']['id']}",
            headers={"Authorization": f"Bearer {outsider['access_key']}"},
            json={"role": "member"},
        )
        removed = client.delete(
            f"/api/v1/admin/organizations/{organization['id']}/members/{member['user']['id']}",
            headers=_admin_headers(),
        )
        after_removal = client.get(
            "/api/v1/orbit/dashboard",
            headers={"Authorization": f"Bearer {member['access_key']}"},
        )

    assert member_dashboard.status_code == 200
    dashboard = member_dashboard.json()
    assert dashboard["organizations"][0]["name"] == "星海研究院"
    assert dashboard["organizations"][0]["membership_role"] == "member"
    assert dashboard["agents"][0]["address"] == "alice@agents.local"
    assert dashboard["agents"][0]["role"] == "viewer"
    assert dashboard["agents"][0]["access_source"] == "organization"
    assert dashboard["agents"][0]["organization"]["slug"] == "fipay-research"
    assert "organization-body-canary" in member_dashboard.text
    assert member_organizations.status_code == 200
    assert member_organizations.json()[0]["slug"] == "fipay-research"

    assert auditor_messages.status_code == 200
    assert auditor_messages.json()[0]["subject"] == "组织研究进度"
    assert auditor_messages.json()[0]["content_body"] is None
    assert auditor_messages.json()[0]["content_redacted"] is True
    assert "organization-body-canary" not in auditor_messages.text

    assert outsider_dashboard.json()["organizations"] == []
    assert outsider_dashboard.json()["agents"] == []
    assert "组织研究进度" not in outsider_dashboard.text
    assert human_cannot_self_join.status_code == 404
    assert removed.status_code == 204
    assert after_removal.json()["organizations"] == []
    assert after_removal.json()["agents"] == []


def test_direct_access_survives_organization_scope_removal(
    settings: Settings,
    database: Database,
) -> None:
    with _client(settings, database) as client:
        organization = _create_organization(client)
        human = _create_human(client, "dual-access@example.com", "双重授权用户")
        agent = _create_agent(client, "dual@agents.local")
        _set_member(client, str(organization["id"]), str(human["user"]["id"]), "auditor")
        _assign_agent(
            client,
            str(organization["id"]),
            str(agent["agent"]["id"]),
        )
        direct = client.put(
            f"/api/v1/admin/humans/{human['user']['id']}/agents/{agent['agent']['id']}",
            headers=_admin_headers(),
            json={"role": "viewer"},
        )
        assert direct.status_code == 200
        before = client.get(
            "/api/v1/orbit/dashboard",
            headers={"Authorization": f"Bearer {human['access_key']}"},
        )
        removed = client.delete(
            f"/api/v1/admin/organizations/{organization['id']}/members/{human['user']['id']}",
            headers=_admin_headers(),
        )
        after = client.get(
            "/api/v1/orbit/dashboard",
            headers={"Authorization": f"Bearer {human['access_key']}"},
        )

    assert before.json()["agents"][0]["role"] == "viewer"
    assert before.json()["agents"][0]["access_source"] == "direct"
    assert before.json()["agents"][0]["organization"]["membership_role"] == "auditor"
    assert removed.status_code == 204
    assert after.json()["organizations"] == []
    assert after.json()["agents"][0]["address"] == "dual@agents.local"
    assert after.json()["agents"][0]["access_source"] == "direct"
    assert after.json()["agents"][0]["organization"] is None
