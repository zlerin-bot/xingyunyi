from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select

from agentpost.config import Settings
from agentpost.control.models import Organization, OrganizationAgent
from agentpost.db import Database
from agentpost.main import create_app
from agentpost.organizations import service as organization_service
from agentpost.organizations.models import OrganizationDomain, OrganizationInvitation

PASSWORD = "correct horse battery staple"
ADMIN_KEY = "admin-secret-admin-secret-admin-secret"
REGISTRATION_TOKEN = "organization-agent-registration"


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


def _admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {ADMIN_KEY}"}


def _create_agent(client: TestClient, address: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/agents",
        headers={"X-Registration-Token": REGISTRATION_TOKEN},
        json={
            "address": address,
            "display_name": address.split("@", 1)[0],
            "capabilities": ["organization-collaboration"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _set_agent_owner(
    client: TestClient,
    *,
    human_id: str,
    agent_id: str,
) -> None:
    response = client.put(
        f"/api/v1/admin/humans/{human_id}/agents/{agent_id}",
        headers=_admin_headers(),
        json={"role": "owner"},
    )
    assert response.status_code == 200, response.text


def _assign_agent_to_organization(
    client: TestClient,
    *,
    organization_id: str,
    agent_id: str,
) -> None:
    response = client.put(
        f"/api/v1/admin/organizations/{organization_id}/agents/{agent_id}",
        headers=_admin_headers(),
    )
    assert response.status_code == 200, response.text


def _register(
    client: TestClient,
    email: str,
    *,
    username: str | None = None,
) -> dict[str, object]:
    challenge = client.post(
        "/api/v1/auth/email/challenges",
        json={"email": email, "purpose": "register"},
    )
    assert challenge.status_code == 202, challenge.text
    payload = challenge.json()
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "challenge_id": payload["challenge_id"],
            "code": payload["test_verification_code"],
            "display_name": email.split("@", 1)[0],
            "password": PASSWORD,
            **({"username": username} if username is not None else {}),
        },
    )
    assert registered.status_code == 201, registered.text
    return registered.json()


def _login(client: TestClient, email: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _logout(client: TestClient, csrf: str) -> None:
    assert (
        client.delete(
            "/api/v1/orbit/session",
            headers={"X-CSRF-Token": csrf},
        ).status_code
        == 204
    )


def _create_organization(client: TestClient, csrf: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/orbit/organizations",
        headers={"X-CSRF-Token": csrf},
        json={"slug": "north-star", "name": "北辰组织", "description": "受控协作"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["membership"]["role"] == "owner"
    return response.json()


def _invite(
    client: TestClient,
    *,
    organization_id: str,
    csrf: str,
    email: str,
    role: str = "member",
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/orbit/organizations/{organization_id}/invitations",
        headers={"X-CSRF-Token": csrf},
        json={"email": email, "role": role},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_owner_creates_organization_and_invitation_is_email_bound_and_one_time(
    settings: Settings,
    database: Database,
) -> None:
    with TestClient(create_app(settings=_runtime(settings), database=database)) as client:
        owner = _register(client, "owner@example.com")
        missing_csrf = client.post(
            "/api/v1/orbit/organizations",
            json={"slug": "denied", "name": "Denied"},
        )
        assert missing_csrf.status_code == 403
        organization = _create_organization(client, str(owner["csrf_token"]))
        organization_id = str(organization["organization"]["id"])
        invitation = _invite(
            client,
            organization_id=organization_id,
            csrf=str(owner["csrf_token"]),
            email="member@example.com",
        )
        raw_token = str(invitation["test_acceptance_token"])
        assert raw_token.startswith("orginv_")
        assert raw_token in invitation["verification_uri"]
        _logout(client, str(owner["csrf_token"]))

        outsider = _register(client, "outsider@example.com")
        wrong_preview = client.post(
            "/api/v1/orbit/organization-invitations/preview",
            json={"token": raw_token},
        )
        assert wrong_preview.status_code == 404
        wrong_user = client.post(
            "/api/v1/orbit/organization-invitations/accept",
            headers={"X-CSRF-Token": outsider["csrf_token"]},
            json={"token": raw_token},
        )
        assert wrong_user.status_code == 404
        _logout(client, str(outsider["csrf_token"]))

        member = _register(client, "member@example.com")
        preview = client.post(
            "/api/v1/orbit/organization-invitations/preview",
            json={"token": raw_token},
        )
        assert preview.status_code == 200, preview.text
        assert preview.json() == {
            "organization_id": organization_id,
            "organization_slug": "north-star",
            "organization_name": "北辰组织",
            "organization_description": "受控协作",
            "role": "member",
            "expires_at": invitation["invitation"]["expires_at"],
        }
        assert client.get("/api/v1/orbit/organizations").json() == []
        with database.session_factory() as session:
            pending = session.scalar(select(OrganizationInvitation))
            assert pending is not None
            assert pending.status == "pending"
        accepted = client.post(
            "/api/v1/orbit/organization-invitations/accept",
            headers={"X-CSRF-Token": member["csrf_token"]},
            json={"token": raw_token},
        )
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["membership"]["role"] == "member"
        replay = client.post(
            "/api/v1/orbit/organization-invitations/accept",
            headers={"X-CSRF-Token": member["csrf_token"]},
            json={"token": raw_token},
        )
        assert replay.status_code == 404

    with database.session_factory() as session:
        stored = session.scalar(select(OrganizationInvitation))
        assert stored is not None
        assert stored.status == "accepted"
        assert stored.token_digest != raw_token
        assert raw_token not in stored.token_digest


def test_username_invitation_is_accepted_inside_orbit_without_email_link(
    settings: Settings,
    database: Database,
) -> None:
    with TestClient(create_app(settings=_runtime(settings), database=database)) as client:
        invitee = _register(client, "site-invitee@example.com")
        invitee_username = str(invitee["user"]["username"])
        invitee_agent = _create_agent(client, "site-invitee-agent@agents.local")
        _set_agent_owner(
            client,
            human_id=str(invitee["user"]["id"]),
            agent_id=str(invitee_agent["agent"]["id"]),
        )
        _logout(client, str(invitee["csrf_token"]))
        owner = _register(client, "site-owner@example.com")
        organization = _create_organization(client, str(owner["csrf_token"]))
        organization_id = str(organization["organization"]["id"])

        created = client.post(
            f"/api/v1/orbit/organizations/{organization_id}/invitations",
            headers={"X-CSRF-Token": owner["csrf_token"]},
            json={"username": invitee_username, "role": "member"},
        )
        assert created.status_code == 201, created.text
        assert created.json()["verification_uri"] is None
        assert created.json()["test_acceptance_token"] is None
        assert created.json()["invitation"]["username"] == invitee_username
        assert created.json()["invitation"]["email"] is None
        invitation_id = created.json()["invitation"]["invitation_id"]
        assert client.get("/api/v1/orbit/organization-invitations").json() == {"items": []}
        wrong_human = client.post(
            f"/api/v1/orbit/organization-invitations/{invitation_id}/accept",
            headers={"X-CSRF-Token": owner["csrf_token"]},
        )
        assert wrong_human.status_code == 404
        _logout(client, str(owner["csrf_token"]))

        invitee_login = _login(client, "site-invitee@example.com")
        inbox = client.get("/api/v1/orbit/organization-invitations")
        assert inbox.status_code == 200, inbox.text
        assert inbox.json()["items"][0]["invitation_id"] == invitation_id
        assert inbox.json()["items"][0]["invited_by_username"] == owner["user"]["username"]
        assert inbox.json()["items"][0]["invited_by_display_name"] == "site-owner"
        accepted = client.post(
            f"/api/v1/orbit/organization-invitations/{invitation_id}/accept",
            headers={"X-CSRF-Token": invitee_login["csrf_token"]},
        )
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["membership"]["role"] == "member"
        assert client.get("/api/v1/orbit/organization-invitations").json() == {"items": []}
        dashboard = client.get("/api/v1/orbit/dashboard")
        assert dashboard.status_code == 200, dashboard.text
        assert organization_id in {str(item["id"]) for item in dashboard.json()["organizations"]}
        members = client.get(f"/api/v1/orbit/organizations/{organization_id}/members")
        assert members.status_code == 200, members.text
        invitee_membership = next(
            item
            for item in members.json()["items"]
            if item["human_user_id"] == invitee["user"]["id"]
        )
        assert invitee_membership["agents"] == [
            {
                "agent_id": invitee_agent["agent"]["id"],
                "address": "site-invitee-agent@agents.local",
                "handle": None,
                "display_name": "site-invitee-agent",
                "participation_source": "default",
            }
        ]


def test_invitation_candidates_include_only_humans_with_real_agent_conversations(
    settings: Settings,
    database: Database,
) -> None:
    with TestClient(create_app(settings=_runtime(settings), database=database)) as client:
        owner = _register(client, "candidate-owner@example.com", username="candidate-owner")
        owner_agent = _create_agent(client, "candidate-owner-agent@agents.local")
        _set_agent_owner(
            client,
            human_id=str(owner["user"]["id"]),
            agent_id=str(owner_agent["agent"]["id"]),
        )

        friend = _register(client, "candidate-friend@example.com", username="candidate-friend")
        friend_agent = _create_agent(client, "candidate-friend-agent@agents.local")
        _set_agent_owner(
            client,
            human_id=str(friend["user"]["id"]),
            agent_id=str(friend_agent["agent"]["id"]),
        )
        outsider = _register(
            client, "candidate-outsider@example.com", username="candidate-outsider"
        )
        outsider_agent = _create_agent(client, "candidate-outsider-agent@agents.local")
        _set_agent_owner(
            client,
            human_id=str(outsider["user"]["id"]),
            agent_id=str(outsider_agent["agent"]["id"]),
        )

        sent = client.post(
            "/api/v1/messages",
            headers={
                "Authorization": f"Bearer {owner_agent['api_key']}",
                "Idempotency-Key": "organization-invitation-candidate",
            },
            json={
                "to": [{"address": friend_agent["agent"]["address"]}],
                "type": "message",
                "subject": "建立真实沟通关系",
                "content": {"format": "text", "body": "用于邀请好友候选测试。"},
            },
        )
        assert sent.status_code == 201, sent.text

        owner_login = _login(client, "candidate-owner@example.com")
        organization = _create_organization(client, str(owner_login["csrf_token"]))
        organization_id = str(organization["organization"]["id"])
        candidates = client.get(
            f"/api/v1/orbit/organizations/{organization_id}/invitation-candidates"
        )
        assert candidates.status_code == 200, candidates.text
        assert [item["username"] for item in candidates.json()["items"]] == ["candidate-friend"]
        assert candidates.json()["items"][0]["display_name"] == "candidate-friend"

        invited = client.post(
            f"/api/v1/orbit/organizations/{organization_id}/invitations",
            headers={"X-CSRF-Token": owner_login["csrf_token"]},
            json={"username": "candidate-friend", "role": "member"},
        )
        assert invited.status_code == 201, invited.text
        assert client.get(
            f"/api/v1/orbit/organizations/{organization_id}/invitation-candidates"
        ).json() == {"items": []}


def test_default_agents_make_a_new_organization_channel_immediately_usable(
    settings: Settings,
    database: Database,
) -> None:
    with TestClient(create_app(settings=_runtime(settings), database=database)) as client:
        owner = _register(client, "default-owner@example.com")
        owner_agent = _create_agent(client, "default-owner-agent@agents.local")
        _set_agent_owner(
            client,
            human_id=str(owner["user"]["id"]),
            agent_id=str(owner_agent["agent"]["id"]),
        )
        organization = _create_organization(client, str(owner["csrf_token"]))
        organization_id = str(organization["organization"]["id"])

        owner_channel = client.get(
            "/api/v1/organization-channel",
            headers={"Authorization": f"Bearer {owner_agent['api_key']}"},
        )
        assert owner_channel.status_code == 200, owner_channel.text
        assert owner_channel.json()["organization_id"] == organization_id

        member = _register(client, "default-member@example.com", username="020")
        member_agent = _create_agent(client, "default-member-agent@agents.local")
        _set_agent_owner(
            client,
            human_id=str(member["user"]["id"]),
            agent_id=str(member_agent["agent"]["id"]),
        )
        handle = client.patch(
            f"/api/v1/orbit/agents/{member_agent['agent']['id']}/handle",
            headers={"X-CSRF-Token": member["csrf_token"]},
            json={"handle": "pa020"},
        )
        assert handle.status_code == 200, handle.text
        set_member = client.put(
            f"/api/v1/admin/organizations/{organization_id}/members/{member['user']['id']}",
            headers=_admin_headers(),
            json={"role": "member"},
        )
        assert set_member.status_code == 200, set_member.text

        members = client.get(f"/api/v1/orbit/organizations/{organization_id}/members")
        assert members.status_code == 200, members.text
        member_agents = {item["human_username"]: item["agents"] for item in members.json()["items"]}
        assert member_agents[owner["user"]["username"]][0]["participation_source"] == "default"
        assert member_agents[member["user"]["username"]][0]["participation_source"] == "default"

        channel_message = client.post(
            f"/api/v1/organizations/{organization_id}/channel/messages",
            headers={
                "Authorization": f"Bearer {owner_agent['api_key']}",
                "Idempotency-Key": "default-participant-channel-message",
            },
            json={
                "type": "message",
                "subject": "默认 Agent 参与组织协作",
                "content": {"format": "text", "body": "请 020 的默认 Agent 回复。"},
                "requested_responder_agent_ids": [member_agent["agent"]["id"]],
            },
        )
        assert channel_message.status_code == 201, channel_message.text
        assert channel_message.json()["recipient_agent_ids"] == [member_agent["agent"]["id"]]

        member_inbox = client.get(
            "/api/v1/inbox",
            headers={"Authorization": f"Bearer {member_agent['api_key']}"},
        )
        assert member_inbox.status_code == 200, member_inbox.text
        assert member_inbox.json()["items"][-1]["content"]["body"] == "请 020 的默认 Agent 回复。"
        channel_message_id = member_inbox.json()["items"][-1]["message_id"]
        reply = client.post(
            f"/api/v1/messages/{channel_message_id}/reply",
            headers={
                "Authorization": f"Bearer {member_agent['api_key']}",
                "Idempotency-Key": "default-participant-channel-reply",
            },
            json={
                "type": "response",
                "subject": "已收到组织协作",
                "content": {"format": "text", "body": "收到，我来处理。"},
            },
        )
        assert reply.status_code == 201, reply.text
        orbit_threads = client.get("/api/v1/orbit/threads")
        assert orbit_threads.status_code == 200, orbit_threads.text
        orbit_summary = next(
            item
            for item in orbit_threads.json()
            if item["thread_id"] == channel_message.json()["thread_id"]
        )
        assert orbit_summary["organization_id"] == organization_id
        assert orbit_summary["organization_name"] == "北辰组织"
        orbit_thread = client.get(f"/api/v1/orbit/threads/{channel_message.json()['thread_id']}")
        assert orbit_thread.status_code == 200, orbit_thread.text
        requested = orbit_thread.json()["messages"][0]["requested_responders"]
        assert requested[0]["owner_username"] == "020"
        assert requested[0]["handle"] == "pa020"


def test_orbit_groups_default_participant_message_by_message_organization(
    settings: Settings,
    database: Database,
) -> None:
    with TestClient(create_app(settings=_runtime(settings), database=database)) as client:
        owner = _register(client, "multi-organization-owner@example.com")
        owner_agent = _create_agent(client, "multi-organization-agent@agents.local")
        _set_agent_owner(
            client,
            human_id=str(owner["user"]["id"]),
            agent_id=str(owner_agent["agent"]["id"]),
        )
        explicit_organization = _create_organization(client, str(owner["csrf_token"]))
        _assign_agent_to_organization(
            client,
            organization_id=str(explicit_organization["organization"]["id"]),
            agent_id=str(owner_agent["agent"]["id"]),
        )
        default_organization = client.post(
            "/api/v1/orbit/organizations",
            headers={"X-CSRF-Token": owner["csrf_token"]},
            json={"slug": "small-group", "name": "小孔", "description": "默认 Agent 参与"},
        )
        assert default_organization.status_code == 201, default_organization.text
        default_organization_id = default_organization.json()["organization"]["id"]

        sent = client.post(
            f"/api/v1/organizations/{default_organization_id}/channel/messages",
            headers={
                "Authorization": f"Bearer {owner_agent['api_key']}",
                "Idempotency-Key": "default-participant-small-group-message",
            },
            json={
                "type": "request",
                "subject": "请确认是否收到小孔群信息",
                "content": {"format": "text", "body": "请在小孔群确认收到。"},
                "requested_responder_agent_ids": [],
            },
        )
        assert sent.status_code == 201, sent.text

        orbit_threads = client.get("/api/v1/orbit/threads")
        assert orbit_threads.status_code == 200, orbit_threads.text
        summary = next(
            item for item in orbit_threads.json() if item["thread_id"] == sent.json()["thread_id"]
        )
        assert summary["organization_id"] == default_organization_id
        assert summary["organization_name"] == "小孔"
        assert summary["organizations"] == [
            {
                "id": default_organization_id,
                "slug": "small-group",
                "name": "小孔",
                "membership_role": None,
            }
        ]

        thread = client.get(f"/api/v1/orbit/threads/{sent.json()['thread_id']}")
        assert thread.status_code == 200, thread.text
        assert thread.json()["organizations"] == summary["organizations"]


def test_owner_assigns_only_owned_agent_and_organization_sees_only_new_messages(
    settings: Settings,
    database: Database,
) -> None:
    with TestClient(create_app(settings=_runtime(settings), database=database)) as client:
        owner = _register(client, "agent-owner@example.com")
        organization = _create_organization(client, str(owner["csrf_token"]))
        organization_id = str(organization["organization"]["id"])
        sender = _create_agent(client, "organization-sender@agents.local")
        recipient = _create_agent(client, "organization-recipient@agents.local")
        observer = _create_agent(client, "organization-observer@agents.local")
        _set_agent_owner(
            client,
            human_id=str(owner["user"]["id"]),
            agent_id=str(sender["agent"]["id"]),
        )

        pre_assignment = client.post(
            "/api/v1/messages",
            headers={
                "Authorization": f"Bearer {sender['api_key']}",
                "Idempotency-Key": "organization-pre-assignment",
            },
            json={
                "to": [{"address": recipient["agent"]["address"]}],
                "type": "message",
                "subject": "加入组织前的私人消息",
                "content": {"format": "text", "body": "pre-assignment-private-body"},
            },
        )
        assert pre_assignment.status_code == 201, pre_assignment.text

        assigned = client.put(
            f"/api/v1/orbit/organizations/{organization_id}/agents/{sender['agent']['id']}",
            headers={"X-CSRF-Token": owner["csrf_token"]},
        )
        assert assigned.status_code == 200, assigned.text
        repeated = client.put(
            f"/api/v1/orbit/organizations/{organization_id}/agents/{sender['agent']['id']}",
            headers={"X-CSRF-Token": owner["csrf_token"]},
        )
        assert repeated.status_code == 200, repeated.text
        _assign_agent_to_organization(
            client,
            organization_id=organization_id,
            agent_id=str(recipient["agent"]["id"]),
        )
        _assign_agent_to_organization(
            client,
            organization_id=organization_id,
            agent_id=str(observer["agent"]["id"]),
        )
        member = _register(client, "organization-reader@example.com")
        set_member = client.put(
            f"/api/v1/admin/organizations/{organization_id}/members/{member['user']['id']}",
            headers=_admin_headers(),
            json={"role": "member"},
        )
        assert set_member.status_code == 200, set_member.text
        member_agent = _create_agent(client, "member-owned@agents.local")
        _set_agent_owner(
            client,
            human_id=str(member["user"]["id"]),
            agent_id=str(member_agent["agent"]["id"]),
        )
        member_assigned = client.put(
            f"/api/v1/orbit/organizations/{organization_id}/agents/{member_agent['agent']['id']}",
            headers={"X-CSRF-Token": member["csrf_token"]},
        )
        assert member_assigned.status_code == 200, member_assigned.text
        members = client.get(f"/api/v1/orbit/organizations/{organization_id}/members")
        assert members.status_code == 200, members.text
        member_entry = next(
            item
            for item in members.json()["items"]
            if item["human_user_id"] == member["user"]["id"]
        )
        assert member_entry["human_username"] == member["user"]["username"]
        assert member_entry["human_display_name"] == member["user"]["display_name"]
        assert [agent["agent_id"] for agent in member_entry["agents"]] == [
            member_agent["agent"]["id"]
        ]
        member_dashboard = client.get("/api/v1/orbit/dashboard")
        assert member_dashboard.status_code == 200
        assert "pre-assignment-private-body" not in member_dashboard.text

        private_post_assignment = client.post(
            "/api/v1/messages",
            headers={
                "Authorization": f"Bearer {sender['api_key']}",
                "Idempotency-Key": "organization-post-assignment",
            },
            json={
                "to": [{"address": recipient["agent"]["address"]}],
                "type": "message",
                "subject": "加入组织后的协作消息",
                "content": {"format": "text", "body": "post-assignment-private-body"},
            },
        )
        assert private_post_assignment.status_code == 201, private_post_assignment.text
        channel_summary = client.get(
            "/api/v1/organization-channel",
            headers={"Authorization": f"Bearer {sender['api_key']}"},
        )
        assert channel_summary.status_code == 200
        assert channel_summary.json()["organization_name"] == "北辰组织"
        assert {agent["agent_id"] for agent in channel_summary.json()["agents"]} == {
            sender["agent"]["id"],
            recipient["agent"]["id"],
            observer["agent"]["id"],
            member_agent["agent"]["id"],
        }
        channel_message = client.post(
            f"/api/v1/organizations/{organization_id}/channel/messages",
            headers={
                "Authorization": f"Bearer {sender['api_key']}",
                "Idempotency-Key": "organization-channel-after-assignment",
            },
            json={
                "type": "message",
                "subject": "组织协作",
                "content": {"format": "text", "body": "post-assignment-channel-body"},
                "requested_responder_agent_ids": [recipient["agent"]["id"]],
            },
        )
        assert channel_message.status_code == 201, channel_message.text
        assert set(channel_message.json()["recipient_agent_ids"]) == {
            recipient["agent"]["id"],
            observer["agent"]["id"],
            member_agent["agent"]["id"],
        }
        assert channel_message.json()["reply_policy"] == "addressed_agents_reply"
        replayed_channel_message = client.post(
            f"/api/v1/organizations/{organization_id}/channel/messages",
            headers={
                "Authorization": f"Bearer {sender['api_key']}",
                "Idempotency-Key": "organization-channel-after-assignment",
            },
            json={
                "type": "message",
                "subject": "组织协作",
                "content": {"format": "text", "body": "post-assignment-channel-body"},
                "requested_responder_agent_ids": [recipient["agent"]["id"]],
            },
        )
        assert replayed_channel_message.status_code == 200
        assert replayed_channel_message.headers["Idempotency-Replayed"] == "true"
        recipient_inbox = client.get(
            "/api/v1/inbox",
            headers={"Authorization": f"Bearer {recipient['api_key']}"},
        )
        assert recipient_inbox.status_code == 200
        channel_inbox_item = recipient_inbox.json()["items"][-1]
        assert channel_inbox_item["metadata"]["context_visible_to_all_assigned_agents"] is True
        assert channel_inbox_item["metadata"]["requested_responder_agent_ids"] == [
            recipient["agent"]["id"]
        ]
        observer_inbox = client.get(
            "/api/v1/inbox",
            headers={"Authorization": f"Bearer {observer['api_key']}"},
        )
        assert observer_inbox.status_code == 200
        observer_item = observer_inbox.json()["items"][-1]
        assert observer_item["content"]["body"] == "post-assignment-channel-body"
        assert observer_item["metadata"]["requested_responder_agent_ids"] == [
            recipient["agent"]["id"]
        ]
        observer_threads = client.get(
            "/api/v1/threads",
            headers={"Authorization": f"Bearer {observer['api_key']}"},
        )
        assert observer_threads.status_code == 200
        channel_thread = next(
            item
            for item in observer_threads.json()["items"]
            if item["thread_id"] == channel_message.json()["thread_id"]
        )
        assert channel_thread["message_count"] == 1
        observer_thread = client.get(
            f"/api/v1/threads/{channel_message.json()['thread_id']}",
            headers={"Authorization": f"Bearer {observer['api_key']}"},
        )
        assert observer_thread.status_code == 200
        assert len(observer_thread.json()["messages"]) == 1
        spoofed_channel = client.post(
            "/api/v1/messages",
            headers={
                "Authorization": f"Bearer {sender['api_key']}",
                "Idempotency-Key": "reserved-channel-metadata",
            },
            json={
                "to": [{"address": recipient["agent"]["address"]}],
                "type": "message",
                "subject": "不能伪造组织频道",
                "content": {"format": "text", "body": "reserved-metadata"},
                "metadata": {"channel_scope": "organization"},
            },
        )
        assert spoofed_channel.status_code == 422
        refreshed = client.get("/api/v1/orbit/dashboard")
        assert refreshed.status_code == 200
        assert "post-assignment-private-body" not in refreshed.text
        assert "post-assignment-channel-body" in refreshed.text
        assert "pre-assignment-private-body" not in refreshed.text


def test_manager_roles_last_owner_and_self_exit_are_enforced(
    settings: Settings,
    database: Database,
) -> None:
    with TestClient(create_app(settings=_runtime(settings), database=database)) as client:
        owner = _register(client, "owner2@example.com")
        organization = _create_organization(client, str(owner["csrf_token"]))
        organization_id = str(organization["organization"]["id"])
        owner_id = str(owner["user"]["id"])
        invitation = _invite(
            client,
            organization_id=organization_id,
            csrf=str(owner["csrf_token"]),
            email="admin@example.com",
            role="admin",
        )
        _logout(client, str(owner["csrf_token"]))
        admin = _register(client, "admin@example.com")
        accepted = client.post(
            "/api/v1/orbit/organization-invitations/accept",
            headers={"X-CSRF-Token": admin["csrf_token"]},
            json={"token": invitation["test_acceptance_token"]},
        )
        assert accepted.status_code == 200

        cannot_invite_admin = client.post(
            f"/api/v1/orbit/organizations/{organization_id}/invitations",
            headers={"X-CSRF-Token": admin["csrf_token"]},
            json={"email": "other@example.com", "role": "admin"},
        )
        assert cannot_invite_admin.status_code == 403
        cannot_remove_owner = client.delete(
            f"/api/v1/orbit/organizations/{organization_id}/members/{owner_id}",
            headers={"X-CSRF-Token": admin["csrf_token"]},
        )
        assert cannot_remove_owner.status_code == 403
        left = client.delete(
            f"/api/v1/orbit/organizations/{organization_id}/membership",
            headers={"X-CSRF-Token": admin["csrf_token"]},
        )
        assert left.status_code == 204

        owner_login = _login(client, "owner2@example.com")
        last_owner_leave = client.delete(
            f"/api/v1/orbit/organizations/{organization_id}/membership",
            headers={"X-CSRF-Token": owner_login["csrf_token"]},
        )
        assert last_owner_leave.status_code == 409
        assert last_owner_leave.json()["error"]["code"] == "LAST_ORGANIZATION_OWNER"


def test_invitation_listing_revocation_and_non_manager_isolation(
    settings: Settings,
    database: Database,
) -> None:
    with TestClient(create_app(settings=_runtime(settings), database=database)) as client:
        owner = _register(client, "owner3@example.com")
        organization = _create_organization(client, str(owner["csrf_token"]))
        organization_id = str(organization["organization"]["id"])
        invitation = _invite(
            client,
            organization_id=organization_id,
            csrf=str(owner["csrf_token"]),
            email="revoked@example.com",
        )
        invitation_id = invitation["invitation"]["invitation_id"]
        listed = client.get(f"/api/v1/orbit/organizations/{organization_id}/invitations")
        assert listed.status_code == 200
        assert "test_acceptance_token" not in listed.text
        revoked = client.delete(
            f"/api/v1/orbit/organizations/{organization_id}/invitations/{invitation_id}",
            headers={"X-CSRF-Token": owner["csrf_token"]},
        )
        assert revoked.status_code == 204
        _logout(client, str(owner["csrf_token"]))

        invited = _register(client, "revoked@example.com")
        rejected = client.post(
            "/api/v1/orbit/organization-invitations/accept",
            headers={"X-CSRF-Token": invited["csrf_token"]},
            json={"token": invitation["test_acceptance_token"]},
        )
        assert rejected.status_code == 404
        hidden = client.get(f"/api/v1/orbit/organizations/{organization_id}/members")
        assert hidden.status_code == 404


def test_owner_can_disband_organization_and_hide_its_group_history(
    settings: Settings,
    database: Database,
) -> None:
    with TestClient(create_app(settings=_runtime(settings), database=database)) as client:
        invitee = _register(client, "disband-invitee@example.com", username="disband-invitee")
        _logout(client, str(invitee["csrf_token"]))
        owner = _register(client, "disband-owner@example.com", username="disband-owner")
        owner_agent = _create_agent(client, "disband-owner-agent@agents.local")
        _set_agent_owner(
            client,
            human_id=str(owner["user"]["id"]),
            agent_id=str(owner_agent["agent"]["id"]),
        )
        organization = _create_organization(client, str(owner["csrf_token"]))
        organization_id = str(organization["organization"]["id"])
        organization_name = str(organization["organization"]["name"])
        assigned = client.put(
            f"/api/v1/orbit/organizations/{organization_id}/agents/{owner_agent['agent']['id']}",
            headers={"X-CSRF-Token": owner["csrf_token"]},
        )
        assert assigned.status_code == 200, assigned.text
        invitation = client.post(
            f"/api/v1/orbit/organizations/{organization_id}/invitations",
            headers={"X-CSRF-Token": owner["csrf_token"]},
            json={"username": "disband-invitee", "role": "member"},
        )
        assert invitation.status_code == 201, invitation.text
        invitation_id = invitation.json()["invitation"]["invitation_id"]
        message = client.post(
            f"/api/v1/organizations/{organization_id}/channel/messages",
            headers={
                "Authorization": f"Bearer {owner_agent['api_key']}",
                "Idempotency-Key": "organization-disband-history",
            },
            json={
                "type": "message",
                "subject": "解散前的组织消息",
                "content": {"format": "text", "body": "archived-organization-body"},
            },
        )
        assert message.status_code == 201, message.text
        assert "archived-organization-body" in client.get("/api/v1/orbit/threads").text

        wrong_name = client.post(
            f"/api/v1/orbit/organizations/{organization_id}/disband",
            headers={"X-CSRF-Token": owner["csrf_token"]},
            json={"confirmation_name": "不是这个组织", "password": PASSWORD},
        )
        assert wrong_name.status_code == 400
        wrong_password = client.post(
            f"/api/v1/orbit/organizations/{organization_id}/disband",
            headers={"X-CSRF-Token": owner["csrf_token"]},
            json={"confirmation_name": organization_name, "password": "wrong password value"},
        )
        assert wrong_password.status_code == 403
        disbanded = client.post(
            f"/api/v1/orbit/organizations/{organization_id}/disband",
            headers={"X-CSRF-Token": owner["csrf_token"]},
            json={"confirmation_name": organization_name, "password": PASSWORD},
        )
        assert disbanded.status_code == 204, disbanded.text
        dashboard = client.get("/api/v1/orbit/dashboard")
        assert organization_id not in {
            str(item["id"]) for item in dashboard.json()["organizations"]
        }
        assert "archived-organization-body" not in client.get("/api/v1/orbit/threads").text
        assert (
            client.get(
                "/api/v1/organization-channel",
                headers={"Authorization": f"Bearer {owner_agent['api_key']}"},
            ).status_code
            == 404
        )

        with database.session_factory() as session:
            stored = session.get(Organization, UUID(organization_id))
            assert stored is not None
            assert stored.status == "archived"
            assert session.get(OrganizationAgent, UUID(str(owner_agent["agent"]["id"]))) is None
            stored_invitation = session.get(OrganizationInvitation, UUID(invitation_id))
            assert stored_invitation is not None
            assert stored_invitation.status == "revoked"


def test_owner_can_transfer_ownership_before_leaving(
    settings: Settings,
    database: Database,
) -> None:
    with TestClient(create_app(settings=_runtime(settings), database=database)) as client:
        owner = _register(client, "transfer-owner@example.com")
        organization = _create_organization(client, str(owner["csrf_token"]))
        organization_id = str(organization["organization"]["id"])
        owner_id = str(owner["user"]["id"])
        invitation = _invite(
            client,
            organization_id=organization_id,
            csrf=str(owner["csrf_token"]),
            email="next-owner@example.com",
        )
        _logout(client, str(owner["csrf_token"]))
        next_owner = _register(client, "next-owner@example.com")
        assert (
            client.post(
                "/api/v1/orbit/organization-invitations/accept",
                headers={"X-CSRF-Token": next_owner["csrf_token"]},
                json={"token": invitation["test_acceptance_token"]},
            ).status_code
            == 200
        )
        next_owner_id = str(next_owner["user"]["id"])
        _logout(client, str(next_owner["csrf_token"]))

        owner_login = _login(client, "transfer-owner@example.com")
        promoted = client.patch(
            f"/api/v1/orbit/organizations/{organization_id}/members/{next_owner_id}",
            headers={"X-CSRF-Token": owner_login["csrf_token"]},
            json={"role": "owner"},
        )
        assert promoted.status_code == 200, promoted.text
        assert promoted.json()["role"] == "owner"
        demoted = client.patch(
            f"/api/v1/orbit/organizations/{organization_id}/members/{owner_id}",
            headers={"X-CSRF-Token": owner_login["csrf_token"]},
            json={"role": "member"},
        )
        assert demoted.status_code == 200, demoted.text
        left = client.delete(
            f"/api/v1/orbit/organizations/{organization_id}/membership",
            headers={"X-CSRF-Token": owner_login["csrf_token"]},
        )
        assert left.status_code == 204
        assert (
            client.get(f"/api/v1/orbit/organizations/{organization_id}/members").status_code == 404
        )


def test_owner_verifies_domain_by_dns_txt_without_storing_raw_proof(
    settings: Settings,
    database: Database,
    monkeypatch,
) -> None:
    with TestClient(create_app(settings=_runtime(settings), database=database)) as client:
        owner = _register(client, "domain-owner@example.com")
        organization = _create_organization(client, str(owner["csrf_token"]))
        organization_id = str(organization["organization"]["id"])

        created = client.post(
            f"/api/v1/orbit/organizations/{organization_id}/domains",
            headers={"X-CSRF-Token": owner["csrf_token"]},
            json={"domain": "Example.COM."},
        )
        assert created.status_code == 201, created.text
        payload = created.json()
        domain_id = str(payload["domain"]["domain_id"])
        raw_value = str(payload["verification_value"])
        assert payload["domain"]["domain"] == "example.com"
        assert payload["domain"]["verification_record_name"] == "_agentpost.example.com"
        assert raw_value.startswith("agentpost-domain-verification=")

        monkeypatch.setattr(
            organization_service,
            "lookup_dns_txt",
            lambda _name, *, timeout: ["wrong-proof"],
        )
        not_verified = client.post(
            f"/api/v1/orbit/organizations/{organization_id}/domains/{domain_id}/verify",
            headers={"X-CSRF-Token": owner["csrf_token"]},
        )
        assert not_verified.status_code == 409

        monkeypatch.setattr(
            organization_service,
            "lookup_dns_txt",
            lambda _name, *, timeout: [raw_value],
        )
        verified = client.post(
            f"/api/v1/orbit/organizations/{organization_id}/domains/{domain_id}/verify",
            headers={"X-CSRF-Token": owner["csrf_token"]},
        )
        assert verified.status_code == 200, verified.text
        assert verified.json()["status"] == "verified"

    with database.session_factory() as session:
        stored = session.scalar(select(OrganizationDomain))
        assert stored is not None
        assert stored.verification_digest != raw_value
        assert raw_value not in stored.verification_digest


def test_domain_claim_is_globally_unique_and_owner_only(
    settings: Settings,
    database: Database,
) -> None:
    with TestClient(create_app(settings=_runtime(settings), database=database)) as client:
        first = _register(client, "first-domain-owner@example.com")
        first_org = _create_organization(client, str(first["csrf_token"]))
        first_org_id = str(first_org["organization"]["id"])
        claimed = client.post(
            f"/api/v1/orbit/organizations/{first_org_id}/domains",
            headers={"X-CSRF-Token": first["csrf_token"]},
            json={"domain": "company.example"},
        )
        assert claimed.status_code == 201, claimed.text
        _logout(client, str(first["csrf_token"]))

        second = _register(client, "second-domain-owner@example.com")
        second_org = client.post(
            "/api/v1/orbit/organizations",
            headers={"X-CSRF-Token": second["csrf_token"]},
            json={"slug": "south-star", "name": "南辰组织"},
        )
        assert second_org.status_code == 201, second_org.text
        second_org_id = str(second_org.json()["organization"]["id"])
        conflict = client.post(
            f"/api/v1/orbit/organizations/{second_org_id}/domains",
            headers={"X-CSRF-Token": second["csrf_token"]},
            json={"domain": "COMPANY.EXAMPLE"},
        )
        assert conflict.status_code == 409

        invitation = _invite(
            client,
            organization_id=second_org_id,
            csrf=str(second["csrf_token"]),
            email="domain-member@example.com",
        )
        _logout(client, str(second["csrf_token"]))
        member = _register(client, "domain-member@example.com")
        assert (
            client.post(
                "/api/v1/orbit/organization-invitations/accept",
                headers={"X-CSRF-Token": member["csrf_token"]},
                json={"token": invitation["test_acceptance_token"]},
            ).status_code
            == 200
        )
        forbidden = client.post(
            f"/api/v1/orbit/organizations/{second_org_id}/domains",
            headers={"X-CSRF-Token": member["csrf_token"]},
            json={"domain": "member.example"},
        )
        assert forbidden.status_code == 403
