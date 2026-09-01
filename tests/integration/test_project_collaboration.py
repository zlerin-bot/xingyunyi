from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select

from agentpost.config import Settings
from agentpost.db import Database
from agentpost.main import create_app
from agentpost.projects.models import Project, ProjectActivity, ProjectMembership

PASSWORD = "correct horse battery staple"
ADMIN_KEY = "admin-secret-admin-secret-admin-secret"
REGISTRATION_TOKEN = "project-agent-registration"


def _runtime(settings: Settings) -> Settings:
    return Settings(
        environment="test",
        database_url=settings.database_url,
        storage_path=settings.storage_path,
        api_key_pepper="test-agent-pepper",
        human_api_key_pepper="test-human-key-pepper",
        human_auth_secret="test-human-auth-secret",
        human_mfa_encryption_key="test-human-mfa-key",
        cursor_secret="test-cursor-secret",
        pairing_secret="test-pairing-secret",
        human_self_service_enabled=True,
        open_registration_enabled=True,
        registration_token=REGISTRATION_TOKEN,
        admin_token=ADMIN_KEY,
        email_delivery_mode="test",
        email_challenge_cooldown_seconds=10,
        public_base_url="https://agentpost.example",
        log_level="WARNING",
    )


def _register(client: TestClient, username: str) -> dict[str, object]:
    email = f"{username}@example.com"
    challenge = client.post(
        "/api/v1/auth/email/challenges", json={"email": email, "purpose": "register"}
    )
    assert challenge.status_code == 202, challenge.text
    challenge_body = challenge.json()
    response = client.post(
        "/api/v1/auth/register",
        json={
            "challenge_id": challenge_body["challenge_id"],
            "code": challenge_body["test_verification_code"],
            "display_name": username,
            "username": username,
            "password": PASSWORD,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _login(client: TestClient, username: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": f"{username}@example.com", "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _create_owned_agent(client: TestClient, *, human_id: str, handle: str) -> dict[str, object]:
    created = client.post(
        "/api/v1/agents",
        headers={"X-Registration-Token": REGISTRATION_TOKEN},
        json={
            "address": f"{handle}@agents.local",
            "display_name": f"{handle}-agent",
            "capabilities": ["research", "document-delivery"],
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assigned = client.put(
        f"/api/v1/admin/humans/{human_id}/agents/{body['agent']['id']}",
        headers={"Authorization": f"Bearer {ADMIN_KEY}"},
        json={"role": "owner"},
    )
    assert assigned.status_code == 200, assigned.text
    return body


def _send_contact(
    client: TestClient,
    *,
    sender_key: str,
    recipient_address: str,
    idempotency_key: str,
    metadata: dict[str, str] | None = None,
) -> None:
    response = client.post(
        "/api/v1/messages",
        headers={
            "Authorization": f"Bearer {sender_key}",
            "Idempotency-Key": idempotency_key,
        },
        json={
            "to": [{"address": recipient_address}],
            "type": "message",
            "subject": "项目协作更新",
            "content": {"format": "text", "body": "协作信息已更新。"},
            "metadata": metadata or {},
        },
    )
    assert response.status_code == 201, response.text


def test_projects_are_persisted_and_multi_invites_use_verified_friends(
    settings: Settings,
    database: Database,
) -> None:
    with TestClient(create_app(settings=_runtime(settings), database=database)) as client:
        owner = _register(client, "project-owner")
        owner_agent = _create_owned_agent(
            client, human_id=str(owner["user"]["id"]), handle="project-owner"
        )
        friend_a = _register(client, "project-friend-a")
        friend_a_agent = _create_owned_agent(
            client, human_id=str(friend_a["user"]["id"]), handle="project-friend-a"
        )
        friend_b = _register(client, "project-friend-b")
        friend_b_agent = _create_owned_agent(
            client, human_id=str(friend_b["user"]["id"]), handle="project-friend-b"
        )
        outsider = _register(client, "project-outsider")

        _send_contact(
            client,
            sender_key=str(owner_agent["api_key"]),
            recipient_address=str(friend_a_agent["agent"]["address"]),
            idempotency_key="project-contact-a",
        )
        _send_contact(
            client,
            sender_key=str(owner_agent["api_key"]),
            recipient_address=str(friend_b_agent["agent"]["address"]),
            idempotency_key="project-contact-b",
        )

        owner_session = _login(client, "project-owner")
        friends = client.get("/api/v1/orbit/friends")
        assert friends.status_code == 200, friends.text
        assert {item["username"] for item in friends.json()["items"]} == {
            "project-friend-a",
            "project-friend-b",
        }
        assert all(item["agents"] for item in friends.json()["items"])

        missing_csrf = client.post("/api/v1/orbit/projects", json={"title": "拒绝创建"})
        assert missing_csrf.status_code == 403
        created = client.post(
            "/api/v1/orbit/projects",
            headers={"X-CSRF-Token": str(owner_session["csrf_token"])},
            json={"title": "客户经营协同", "description": "统一跟踪项目协作信息"},
        )
        assert created.status_code == 201, created.text
        project = created.json()
        project_id = project["project_id"]
        project_uuid = UUID(project_id)
        assert project["membership_role"] == "owner"
        assert project["active_member_count"] == 1
        assert project["members"][0]["agent"]["agent_id"] == owner_agent["agent"]["id"]

        candidates = client.get(f"/api/v1/orbit/projects/{project_id}/invite-candidates")
        assert candidates.status_code == 200, candidates.text
        assert len(candidates.json()["items"]) == 2

        unrelated_invite = client.post(
            f"/api/v1/orbit/projects/{project_id}/members",
            headers={"X-CSRF-Token": str(owner_session["csrf_token"])},
            json={"human_user_ids": [outsider["user"]["id"]]},
        )
        assert unrelated_invite.status_code == 404

        invited = client.post(
            f"/api/v1/orbit/projects/{project_id}/members",
            headers={"X-CSRF-Token": str(owner_session["csrf_token"])},
            json={
                "human_user_ids": [
                    friend_a["user"]["id"],
                    friend_b["user"]["id"],
                ]
            },
        )
        assert invited.status_code == 200, invited.text
        assert invited.json()["invited_member_count"] == 2
        assert sum(item["kind"] == "member_invited" for item in invited.json()["activities"]) == 2

        friend_session = _login(client, "project-friend-a")
        friend_projects = client.get("/api/v1/orbit/projects")
        assert friend_projects.status_code == 200, friend_projects.text
        assert friend_projects.json()["items"][0]["membership_status"] == "invited"
        accepted = client.post(
            f"/api/v1/orbit/projects/{project_id}/accept",
            headers={"X-CSRF-Token": str(friend_session["csrf_token"])},
        )
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["membership_status"] == "active"

        _send_contact(
            client,
            sender_key=str(friend_a_agent["api_key"]),
            recipient_address=str(owner_agent["agent"]["address"]),
            idempotency_key="project-linked-update",
            metadata={"project_id": project_id},
        )
        refreshed = client.get(f"/api/v1/orbit/projects/{project_id}")
        assert refreshed.status_code == 200, refreshed.text
        linked = next(
            item for item in refreshed.json()["activities"] if item["kind"] == "agent_update"
        )
        assert linked["agent_id"] == friend_a_agent["agent"]["id"]
        assert linked["security_label"] == "external_agent_content"

        with database.session_factory() as session:
            assert session.scalar(select(Project).where(Project.id == project_uuid)) is not None
            assert (
                len(
                    session.scalars(
                        select(ProjectMembership).where(
                            ProjectMembership.project_id == project_uuid
                        )
                    ).all()
                )
                == 3
            )
            activity_types = set(
                session.scalars(
                    select(ProjectActivity.activity_type).where(
                        ProjectActivity.project_id == project_uuid
                    )
                )
            )
            assert {"created", "member_invited", "member_joined"}.issubset(activity_types)


def test_project_owner_can_archive_and_restore(
    settings: Settings,
    database: Database,
) -> None:
    with TestClient(create_app(settings=_runtime(settings), database=database)) as client:
        _register(client, "status-owner")
        owner_session = _login(client, "status-owner")
        created = client.post(
            "/api/v1/orbit/projects",
            headers={"X-CSRF-Token": str(owner_session["csrf_token"])},
            json={"title": "状态流转"},
        )
        assert created.status_code == 201, created.text
        project_id = created.json()["project_id"]
        archived = client.patch(
            f"/api/v1/orbit/projects/{project_id}/status",
            headers={"X-CSRF-Token": str(owner_session["csrf_token"])},
            json={"status": "archived"},
        )
        assert archived.status_code == 200, archived.text
        assert archived.json()["status"] == "archived"
        restored = client.patch(
            f"/api/v1/orbit/projects/{project_id}/status",
            headers={"X-CSRF-Token": str(owner_session["csrf_token"])},
            json={"status": "active"},
        )
        assert restored.status_code == 200, restored.text
        assert restored.json()["status"] == "active"
        assert [item["kind"] for item in restored.json()["activities"][:2]] == [
            "restored",
            "archived",
        ]
