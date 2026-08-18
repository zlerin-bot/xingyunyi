from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse
from uuid import UUID

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import select

from agentpost.config import Settings
from agentpost.control.models import HumanSession, HumanUser, OrganizationMembership
from agentpost.db import Database
from agentpost.main import create_app
from agentpost.organizations import service as organization_service
from agentpost.sso.models import OrganizationOidcIdentity, OrganizationOidcProvider

PASSWORD = "correct horse battery staple"
ISSUER = "https://idp.company.example"


class FakeOidcProvider:
    def __init__(self) -> None:
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.private_key.public_key()))
        self.jwk.update({"kid": "test-key", "use": "sig", "alg": "RS256"})
        self.nonce = ""
        self.email = "employee@company.example"
        self.subject = "employee-subject"
        self.email_verified = True
        self.token_requests = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path.endswith(
            "/.well-known/openid-configuration"
        ):
            return httpx.Response(
                200,
                json={
                    "issuer": ISSUER,
                    "authorization_endpoint": f"{ISSUER}/authorize",
                    "token_endpoint": f"{ISSUER}/token",
                    "jwks_uri": f"{ISSUER}/jwks",
                    "token_endpoint_auth_methods_supported": ["client_secret_post"],
                },
            )
        if request.method == "GET" and request.url.path == "/jwks":
            return httpx.Response(200, json={"keys": [self.jwk]})
        if request.method == "POST" and request.url.path == "/token":
            self.token_requests += 1
            form = parse_qs(request.content.decode())
            assert form["client_id"] == ["company-client"]
            assert form["client_secret"] == ["super-secret-client-value"]
            assert form["grant_type"] == ["authorization_code"]
            assert len(form["code_verifier"][0]) >= 43
            now = datetime.now(UTC)
            token = jwt.encode(
                {
                    "iss": ISSUER,
                    "aud": "company-client",
                    "sub": self.subject,
                    "email": self.email,
                    "email_verified": self.email_verified,
                    "name": "Enterprise Employee",
                    "nonce": self.nonce,
                    "amr": ["pwd", "mfa"],
                    "iat": now,
                    "exp": now + timedelta(minutes=5),
                },
                self.private_key,
                algorithm="RS256",
                headers={"kid": "test-key"},
            )
            return httpx.Response(200, json={"id_token": token, "token_type": "Bearer"})
        return httpx.Response(404)


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
        enterprise_oidc_enabled=True,
        oidc_allowed_issuers=ISSUER,
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
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "challenge_id": challenge.json()["challenge_id"],
            "code": challenge.json()["test_verification_code"],
            "display_name": email.split("@", 1)[0],
            "password": PASSWORD,
        },
    )
    assert registered.status_code == 201, registered.text
    return registered.json()


def _organization_with_verified_domain(
    client: TestClient,
    monkeypatch,
    *,
    csrf: str,
) -> str:
    created = client.post(
        "/api/v1/orbit/organizations",
        headers={"X-CSRF-Token": csrf},
        json={"slug": "enterprise", "name": "Enterprise"},
    )
    assert created.status_code == 201, created.text
    organization_id = created.json()["organization"]["id"]
    claim = client.post(
        f"/api/v1/orbit/organizations/{organization_id}/domains",
        headers={"X-CSRF-Token": csrf},
        json={"domain": "company.example"},
    )
    assert claim.status_code == 201, claim.text
    raw_proof = claim.json()["verification_value"]
    monkeypatch.setattr(
        organization_service,
        "lookup_dns_txt",
        lambda _name, *, timeout: [raw_proof],
    )
    verified = client.post(
        f"/api/v1/orbit/organizations/{organization_id}/domains/"
        f"{claim.json()['domain']['domain_id']}/verify",
        headers={"X-CSRF-Token": csrf},
    )
    assert verified.status_code == 200, verified.text
    return organization_id


def _configure_provider(
    client: TestClient,
    *,
    organization_id: str,
    csrf: str,
) -> str:
    configured = client.post(
        f"/api/v1/orbit/organizations/{organization_id}/oidc-providers",
        headers={"X-CSRF-Token": csrf},
        json={
            "display_name": "Company SSO",
            "issuer": ISSUER,
            "client_id": "company-client",
            "client_secret": "super-secret-client-value",
        },
    )
    assert configured.status_code == 201, configured.text
    assert "secret" not in configured.text.casefold()
    return configured.json()["provider_id"]


def _start_login(client: TestClient, provider_id: str, fake: FakeOidcProvider) -> str:
    started = client.post(f"/api/v1/auth/oidc/{provider_id}/start")
    assert started.status_code == 200, started.text
    parsed = urlparse(started.json()["authorization_url"])
    query = parse_qs(parsed.query)
    assert query["code_challenge_method"] == ["S256"]
    assert query["redirect_uri"] == ["https://agentpost.example/api/v1/auth/oidc/callback"]
    fake.nonce = query["nonce"][0]
    return query["state"][0]


def test_enterprise_oidc_auto_provisions_verified_domain_member_and_session(
    settings: Settings,
    database: Database,
    monkeypatch,
) -> None:
    fake = FakeOidcProvider()
    app = create_app(settings=_runtime(settings), database=database)
    app.state.oidc_http_transport = httpx.MockTransport(fake.handler)
    with TestClient(app) as client:
        owner = _register(client, "owner@company.example")
        organization_id = _organization_with_verified_domain(
            client,
            monkeypatch,
            csrf=str(owner["csrf_token"]),
        )
        provider_id = _configure_provider(
            client,
            organization_id=organization_id,
            csrf=str(owner["csrf_token"]),
        )
        discovery = client.post(
            "/api/v1/auth/oidc/providers",
            json={"email": "employee@company.example"},
        )
        assert discovery.status_code == 200
        assert [item["provider_id"] for item in discovery.json()["items"]] == [provider_id]
        state = _start_login(client, provider_id, fake)
        callback = client.get(
            "/api/v1/auth/oidc/callback",
            params={"code": "authorization-code", "state": state},
            follow_redirects=False,
        )
        assert callback.status_code == 303, callback.text
        assert callback.headers["location"] == "/orbit?oidc=success"
        assert "httponly" in callback.headers["set-cookie"].casefold()
        profile = client.get("/api/v1/orbit/me")
        assert profile.status_code == 200, profile.text
        assert profile.json()["email"] == "employee@company.example"
        replay = client.get(
            "/api/v1/auth/oidc/callback",
            params={"code": "authorization-code", "state": state},
            follow_redirects=False,
        )
        assert replay.status_code == 400
        assert replay.json()["error"]["code"] == "OIDC_STATE_INVALID"

    with database.session_factory() as session:
        provider = session.get(OrganizationOidcProvider, UUID(provider_id))
        assert provider is not None
        assert provider.encrypted_client_secret != "super-secret-client-value"
        assert "super-secret-client-value" not in provider.encrypted_client_secret
        employee = session.scalar(
            select(HumanUser).where(HumanUser.email == "employee@company.example")
        )
        assert employee is not None
        membership = session.scalar(
            select(OrganizationMembership).where(
                OrganizationMembership.organization_id == UUID(organization_id),
                OrganizationMembership.human_user_id == employee.id,
            )
        )
        assert membership is not None and membership.role == "member"
        identity = session.scalar(
            select(OrganizationOidcIdentity).where(
                OrganizationOidcIdentity.human_user_id == employee.id
            )
        )
        assert identity is not None
        browser_session = session.scalar(
            select(HumanSession)
            .where(HumanSession.human_user_id == employee.id)
            .order_by(HumanSession.created_at.desc())
        )
        assert browser_session is not None
        assert browser_session.auth_method == "enterprise_oidc"
        assert browser_session.mfa_authenticated_at is not None


def test_existing_email_requires_explicit_password_bound_link(
    settings: Settings,
    database: Database,
    monkeypatch,
) -> None:
    fake = FakeOidcProvider()
    app = create_app(settings=_runtime(settings), database=database)
    app.state.oidc_http_transport = httpx.MockTransport(fake.handler)
    with TestClient(app) as client:
        owner = _register(client, "owner@company.example")
        organization_id = _organization_with_verified_domain(
            client,
            monkeypatch,
            csrf=str(owner["csrf_token"]),
        )
        provider_id = _configure_provider(
            client,
            organization_id=organization_id,
            csrf=str(owner["csrf_token"]),
        )
        existing = _register(client, "employee@company.example")
        with database.session_factory() as session:
            user = session.scalar(
                select(HumanUser).where(HumanUser.email == "employee@company.example")
            )
            session.add(
                OrganizationMembership(
                    organization_id=UUID(organization_id),
                    human_user_id=user.id,
                    role="member",
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            )
            session.commit()

        state = _start_login(client, provider_id, fake)
        collision = client.get(
            "/api/v1/auth/oidc/callback",
            params={"code": "collision", "state": state},
            follow_redirects=False,
        )
        assert collision.status_code == 409
        assert collision.json()["error"]["code"] == "OIDC_ACCOUNT_LINK_REQUIRED"
        no_csrf = client.post(
            f"/api/v1/orbit/organizations/{organization_id}/oidc-providers/{provider_id}/link",
            json={"password": PASSWORD},
        )
        assert no_csrf.status_code == 403
        bad_password = client.post(
            f"/api/v1/orbit/organizations/{organization_id}/oidc-providers/{provider_id}/link",
            headers={"X-CSRF-Token": existing["csrf_token"]},
            json={"password": "this password is wrong"},
        )
        assert bad_password.status_code == 401
        link = client.post(
            f"/api/v1/orbit/organizations/{organization_id}/oidc-providers/{provider_id}/link",
            headers={"X-CSRF-Token": existing["csrf_token"]},
            json={"password": PASSWORD},
        )
        assert link.status_code == 200, link.text
        query = parse_qs(urlparse(link.json()["authorization_url"]).query)
        fake.nonce = query["nonce"][0]
        linked = client.get(
            "/api/v1/auth/oidc/callback",
            params={"code": "link", "state": query["state"][0]},
            follow_redirects=False,
        )
        assert linked.status_code == 303, linked.text

    with database.session_factory() as session:
        existing_user = session.scalar(
            select(HumanUser).where(HumanUser.email == "employee@company.example")
        )
        identities = session.scalars(
            select(OrganizationOidcIdentity).where(
                OrganizationOidcIdentity.human_user_id == existing_user.id
            )
        ).all()
        assert len(identities) == 1


def test_oidc_management_requires_verified_domain_allowlist_and_owner(
    settings: Settings,
    database: Database,
    monkeypatch,
) -> None:
    fake = FakeOidcProvider()
    runtime = _runtime(settings)
    app = create_app(settings=runtime, database=database)
    app.state.oidc_http_transport = httpx.MockTransport(fake.handler)
    with TestClient(app) as client:
        owner = _register(client, "owner@company.example")
        created = client.post(
            "/api/v1/orbit/organizations",
            headers={"X-CSRF-Token": owner["csrf_token"]},
            json={"slug": "unverified", "name": "Unverified"},
        )
        organization_id = created.json()["organization"]["id"]
        missing_domain = client.post(
            f"/api/v1/orbit/organizations/{organization_id}/oidc-providers",
            headers={"X-CSRF-Token": owner["csrf_token"]},
            json={
                "display_name": "Company SSO",
                "issuer": ISSUER,
                "client_id": "company-client",
                "client_secret": "super-secret-client-value",
            },
        )
        assert missing_domain.status_code == 409
        other_issuer = dict(
            display_name="Bad",
            issuer="https://not-allowed.example",
            client_id="company-client",
            client_secret="super-secret-client-value",
        )
        organization_id = _organization_with_verified_domain(
            client,
            monkeypatch,
            csrf=str(owner["csrf_token"]),
        )
        rejected = client.post(
            f"/api/v1/orbit/organizations/{organization_id}/oidc-providers",
            headers={"X-CSRF-Token": owner["csrf_token"]},
            json=other_issuer,
        )
        assert rejected.status_code == 422
        provider_id = _configure_provider(
            client,
            organization_id=organization_id,
            csrf=str(owner["csrf_token"]),
        )
        disabled = client.delete(
            f"/api/v1/orbit/organizations/{organization_id}/oidc-providers/{provider_id}",
            headers={"X-CSRF-Token": owner["csrf_token"]},
        )
        assert disabled.status_code == 204
        assert client.post(f"/api/v1/auth/oidc/{provider_id}/start").status_code == 404


def test_enterprise_oidc_surface_is_hidden_when_disabled(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/oidc/providers",
        json={"email": "employee@company.example"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ENTERPRISE_OIDC_DISABLED"
    page = client.get("/orbit")
    script = client.get("/orbit/app.js")
    assert 'id="discover-oidc"' in page.text
    assert 'id="organization-oidc-client-secret"' in page.text
    assert 'id="sso-link-dialog"' in page.text
    assert 'autocomplete="new-password"' in page.text
    assert "/api/v1/auth/oidc/providers" in script.text
    assert "/link`" in script.text
    assert 'organizationOidcClientSecret.value = ""' in script.text
    assert "localStorage" not in script.text
