from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from agentpost.config import Settings
from agentpost.db import Database
from agentpost.main import create_app
from agentpost.organizations import service as organization_service
from agentpost.organizations.models import OrganizationDomain, OrganizationInvitation

PASSWORD = "correct horse battery staple"


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
        email_delivery_mode="test",
        email_challenge_cooldown_seconds=10,
        public_base_url="https://agentpost.example",
        log_level="WARNING",
    )


def _register(client: TestClient, email: str) -> dict[str, object]:
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
