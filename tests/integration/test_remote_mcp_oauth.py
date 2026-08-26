from __future__ import annotations

import base64
import hashlib
from typing import Any
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from agentpost.config import Settings
from agentpost.db import Database
from agentpost.main import create_app
from agentpost.oauth.constants import DEVICE_GRANT_TYPE, OFFICIAL_REMOTE_MCP_CLIENT_ID
from agentpost.oauth.models import OAuthAccessToken, OAuthRefreshToken

ADMIN_KEY = "admin-secret-admin-secret-admin-secret"


def _settings(settings: Settings) -> Settings:
    return Settings(
        environment="test",
        database_url=settings.database_url,
        storage_path=settings.storage_path,
        api_key_pepper="oauth-agent-pepper",
        human_api_key_pepper="oauth-human-pepper",
        cursor_secret="oauth-cursor-secret",
        pairing_secret="oauth-pairing-secret",
        oauth_token_pepper="oauth-token-pepper",
        registration_token="registration-secret",
        admin_token=ADMIN_KEY,
        pairing_enabled=True,
        remote_mcp_oauth_enabled=True,
        manus_remote_mcp_enabled=True,
        managed_agent_domain="agents.local",
        public_base_url="https://agentpost.example",
        pairing_ttl_seconds=600,
        pairing_poll_interval_seconds=5,
        oauth_access_token_ttl_seconds=900,
        oauth_refresh_token_ttl_seconds=86400,
        log_level="WARNING",
    )


def _human(client: TestClient) -> dict[str, Any]:
    created = client.post(
        "/api/v1/admin/humans",
        headers={"Authorization": f"Bearer {ADMIN_KEY}"},
        json={"email": "oauth-owner@example.com", "display_name": "OAuth Owner"},
    )
    assert created.status_code == 201, created.text
    result = created.json()
    login = client.post(
        "/api/v1/orbit/session",
        headers={"Authorization": f"Bearer {result['access_key']}"},
    )
    assert login.status_code == 201, login.text
    result["csrf_token"] = login.json()["csrf_token"]
    return result


def _device_authorization(client: TestClient) -> dict[str, Any]:
    response = client.post(
        "/oauth/device_authorization",
        data={
            "client_id": OFFICIAL_REMOTE_MCP_CLIENT_ID,
            "scope": "agentpost.messaging",
            "resource": "https://agentpost.example/mcp",
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers["Cache-Control"] == "no-store"
    payload = response.json()
    query = parse_qs(urlsplit(payload["verification_uri_complete"]).query)
    payload["pairing_id"] = query["pairing"][0]
    assert query["code"][0] == payload["user_code"]
    return payload


def _authorize_device(
    client: TestClient,
    *,
    human: dict[str, Any],
    device: dict[str, Any],
    existing_agent_id: str | None = None,
) -> dict[str, Any]:
    confirmation = client.post(
        f"/api/v1/orbit/pairings/{device['pairing_id']}/confirmation",
        headers={
            "Authorization": f"Bearer {human['access_key']}",
            "X-CSRF-Token": human["csrf_token"],
        },
        json={"intent": "approve", "user_code": device["user_code"]},
    )
    assert confirmation.status_code == 200, confirmation.text
    decision = client.post(
        f"/api/v1/orbit/pairings/{device['pairing_id']}/decision",
        headers={
            "X-CSRF-Token": human["csrf_token"],
            "X-Human-Confirmation": confirmation.json()["confirmation_token"],
            "Idempotency-Key": f"oauth-owner-decision-{device['pairing_id']}",
        },
        json=(
            {"decision": "approved", "existing_agent_id": existing_agent_id}
            if existing_agent_id
            else {
                "decision": "approved",
                "local_agent_id": "remote-mcp-agent",
                "display_name": "Remote MCP Agent",
            }
        ),
    )
    assert decision.status_code == 200, decision.text
    return decision.json()


def _exchange(client: TestClient, device_code: str):
    return client.post(
        "/oauth/token",
        data={
            "grant_type": DEVICE_GRANT_TYPE,
            "client_id": OFFICIAL_REMOTE_MCP_CLIENT_ID,
            "device_code": device_code,
        },
    )


def test_oauth_device_flow_issues_scoped_rotating_tokens(
    settings: Settings,
    database: Database,
) -> None:
    runtime = _settings(settings)
    with TestClient(create_app(settings=runtime, database=database)) as client:
        metadata = client.get("/.well-known/oauth-authorization-server")
        protected = client.get("/.well-known/oauth-protected-resource")
        assert metadata.status_code == protected.status_code == 200
        assert DEVICE_GRANT_TYPE in metadata.json()["grant_types_supported"]
        assert protected.json()["resource"] == "https://agentpost.example/mcp"

        invalid_client = client.post(
            "/oauth/device_authorization",
            data={"client_id": "unknown-client", "scope": "agentpost.messaging"},
        )
        assert invalid_client.status_code == 401
        assert invalid_client.json()["error"] == "invalid_client"

        device = _device_authorization(client)
        pending = _exchange(client, device["device_code"])
        too_fast = _exchange(client, device["device_code"])
        assert pending.status_code == too_fast.status_code == 400
        assert pending.json()["error"] == "authorization_pending"
        assert too_fast.json()["error"] == "slow_down"
        assert too_fast.headers["Retry-After"]

        legacy_exchange = client.post(
            "/api/v1/connect/pairings/token",
            json={"device_code": device["device_code"]},
        )
        assert legacy_exchange.status_code == 404

        human = _human(client)
        _authorize_device(client, human=human, device=device)
        issued = _exchange(client, device["device_code"])
        replayed_exchange = _exchange(client, device["device_code"])
        assert issued.status_code == replayed_exchange.status_code == 200
        token = issued.json()
        assert token["access_token"].startswith("oat_")
        assert token["refresh_token"].startswith("ort_")
        assert token["access_token"] == replayed_exchange.json()["access_token"]
        assert token["expires_in"] == 900
        assert token["scope"] == "agentpost.messaging"
        assert "agt_" not in issued.text

        bearer = {"Authorization": f"Bearer {token['access_token']}"}
        inbox = client.get("/api/v1/inbox?status=unread", headers=bearer)
        token_info = client.get("/api/v1/oauth/token-info", headers=bearer)
        forbidden = client.post(
            "/api/v1/connect/heartbeat",
            headers=bearer,
            json={"health_status": "healthy"},
        )
        assert inbox.status_code == 200
        assert token_info.status_code == 200
        assert token_info.json()["client_id"] == OFFICIAL_REMOTE_MCP_CLIENT_ID
        assert token_info.json()["scope"] == "agentpost.messaging"
        assert forbidden.status_code == 403
        assert forbidden.json()["error"]["code"] == "INSUFFICIENT_SCOPE"

        refreshed = client.post(
            "/oauth/token",
            data={
                "grant_type": "refresh_token",
                "client_id": OFFICIAL_REMOTE_MCP_CLIENT_ID,
                "refresh_token": token["refresh_token"],
            },
        )
        assert refreshed.status_code == 200, refreshed.text
        replacement = refreshed.json()
        assert replacement["access_token"] != token["access_token"]
        assert replacement["refresh_token"] != token["refresh_token"]
        assert client.get("/api/v1/inbox", headers=bearer).status_code == 401
        assert (
            client.get(
                "/api/v1/inbox",
                headers={"Authorization": f"Bearer {replacement['access_token']}"},
            ).status_code
            == 200
        )

        replay_attack = client.post(
            "/oauth/token",
            data={
                "grant_type": "refresh_token",
                "client_id": OFFICIAL_REMOTE_MCP_CLIENT_ID,
                "refresh_token": token["refresh_token"],
            },
        )
        assert replay_attack.status_code == 400
        assert replay_attack.json()["error"] == "invalid_grant"
        assert (
            client.get(
                "/api/v1/inbox",
                headers={"Authorization": f"Bearer {replacement['access_token']}"},
            ).status_code
            == 401
        )

    with database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(OAuthAccessToken)) == 2
        assert session.scalar(select(func.count()).select_from(OAuthRefreshToken)) == 2
        for access in session.scalars(select(OAuthAccessToken)).all():
            assert access.token_digest not in issued.text
            assert access.revoked_at is not None
        for refresh in session.scalars(select(OAuthRefreshToken)).all():
            assert refresh.token_digest not in issued.text
            assert refresh.revoked_at is not None


def _pkce() -> tuple[str, str]:
    verifier = "manus-pkce-verifier-abcdefghijklmnopqrstuvwxyz-0123456789"
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge.decode().rstrip("=")


def _register_manus_client(client: TestClient) -> dict[str, Any]:
    registered = client.post(
        "/oauth/register",
        json={
            "client_name": "Manus Custom MCP",
            "application_type": "native",
            "redirect_uris": ["https://manus.example/oauth/callback"],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
            "scope": "agentpost.messaging",
        },
    )
    assert registered.status_code == 201, registered.text
    assert registered.json()["client_secret_expires_at"] == 0
    assert "client_secret" not in registered.json()
    return registered.json()


def test_dynamic_client_registration_rejects_secret_and_unsafe_redirects(
    settings: Settings,
    database: Database,
) -> None:
    runtime = _settings(settings)
    with TestClient(create_app(settings=runtime, database=database)) as client:
        unsafe = client.post(
            "/oauth/register",
            json={
                "client_name": "Unsafe Manus",
                "redirect_uris": ["http://remote.example/callback"],
            },
        )
        confidential = client.post(
            "/oauth/register",
            json={
                "client_name": "Secret Manus",
                "redirect_uris": ["https://manus.example/callback"],
                "token_endpoint_auth_method": "client_secret_post",
            },
        )
    assert unsafe.status_code == 400
    assert unsafe.json()["error"] == "invalid_redirect_uri"
    assert confidential.status_code == 422


def _start_manus_authorization(
    client: TestClient,
    *,
    client_id: str,
    resource: str,
    state: str,
) -> tuple[dict[str, Any], str]:
    verifier, challenge = _pkce()
    started = client.get(
        "/oauth/authorize",
        params={
            "client_id": client_id,
            "redirect_uri": "https://manus.example/oauth/callback",
            "response_type": "code",
            "scope": "agentpost.messaging",
            "resource": resource,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        },
        follow_redirects=False,
    )
    assert started.status_code == 302, started.text
    query = parse_qs(urlsplit(started.headers["Location"]).query)
    return {
        "pairing_id": query["pairing"][0],
        "user_code": query["code"][0],
        "oauth_request": query["oauth_request"][0],
    }, verifier


def test_manus_authorization_code_pkce_creates_and_reconnects_stable_agent(
    settings: Settings,
    database: Database,
) -> None:
    runtime = _settings(settings)
    new_resource = "https://agentpost.example/mcp/connect/new-40000000-0000-0000-0000-000000000001"
    with TestClient(create_app(settings=runtime, database=database)) as client:
        metadata = client.get("/.well-known/oauth-authorization-server").json()
        protected = client.get(
            "/.well-known/oauth-protected-resource/mcp/connect/"
            "new-40000000-0000-0000-0000-000000000001"
        )
        assert metadata["authorization_endpoint"].startswith("https://")
        assert metadata["registration_endpoint"].startswith("https://")
        assert metadata["code_challenge_methods_supported"] == ["S256"]
        assert protected.status_code == 200
        assert protected.json()["resource"] == new_resource

        dynamic_client = _register_manus_client(client)
        human = _human(client)
        authorization, verifier = _start_manus_authorization(
            client,
            client_id=dynamic_client["client_id"],
            resource=new_resource,
            state="manus-state-new",
        )
        decision = _authorize_device(client, human=human, device=authorization)
        agent_id = decision["pairing"]["agent"]["id"]
        completed = client.post(
            "/api/v1/orbit/oauth/authorize/complete",
            params={"authorization_request": authorization["oauth_request"]},
            headers={"X-CSRF-Token": human["csrf_token"]},
        )
        assert completed.status_code == 200
        callback = parse_qs(urlsplit(completed.json()["redirect_to"]).query)
        assert callback["state"] == ["manus-state-new"]
        wrong_verifier = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": dynamic_client["client_id"],
                "code": callback["code"][0],
                "redirect_uri": "https://manus.example/oauth/callback",
                "code_verifier": "wrong-pkce-verifier-abcdefghijklmnopqrstuvwxyz-0123456789",
                "resource": new_resource,
            },
        )
        assert wrong_verifier.status_code == 400
        assert wrong_verifier.json()["error"] == "invalid_grant"
        issued = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": dynamic_client["client_id"],
                "code": callback["code"][0],
                "redirect_uri": "https://manus.example/oauth/callback",
                "code_verifier": verifier,
                "resource": new_resource,
            },
        )
        assert issued.status_code == 200, issued.text
        replayed_code = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": dynamic_client["client_id"],
                "code": callback["code"][0],
                "redirect_uri": "https://manus.example/oauth/callback",
                "code_verifier": verifier,
                "resource": new_resource,
            },
        )
        assert replayed_code.status_code == 400
        assert replayed_code.json()["error"] == "invalid_grant"
        bearer = {"Authorization": f"Bearer {issued.json()['access_token']}"}
        assert client.get("/api/v1/inbox", headers=bearer).status_code == 200
        assert _exchange(client, authorization.get("device_code", "unused")).status_code == 422
        _, duplicate_challenge = _pkce()
        duplicate_intent = client.get(
            "/oauth/authorize",
            params={
                "client_id": dynamic_client["client_id"],
                "redirect_uri": "https://manus.example/oauth/callback",
                "response_type": "code",
                "scope": "agentpost.messaging",
                "resource": new_resource,
                "state": "duplicate-new-intent",
                "code_challenge": duplicate_challenge,
                "code_challenge_method": "S256",
            },
            follow_redirects=False,
        )
        assert duplicate_intent.status_code == 400
        assert duplicate_intent.json()["error"] == "invalid_target"

        reconnect_resource = f"https://agentpost.example/mcp/connect/agent-{agent_id}"
        reconnect, reconnect_verifier = _start_manus_authorization(
            client,
            client_id=dynamic_client["client_id"],
            resource=reconnect_resource,
            state="manus-state-reconnect",
        )
        migrated = _authorize_device(
            client,
            human=human,
            device=reconnect,
            existing_agent_id=agent_id,
        )
        assert migrated["pairing"]["agent"]["id"] == agent_id
        completed_reconnect = client.post(
            "/api/v1/orbit/oauth/authorize/complete",
            params={"authorization_request": reconnect["oauth_request"]},
            headers={"X-CSRF-Token": human["csrf_token"]},
        )
        reconnect_code = parse_qs(urlsplit(completed_reconnect.json()["redirect_to"]).query)[
            "code"
        ][0]
        reissued = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": dynamic_client["client_id"],
                "code": reconnect_code,
                "redirect_uri": "https://manus.example/oauth/callback",
                "code_verifier": reconnect_verifier,
                "resource": reconnect_resource,
            },
        )
        assert reissued.status_code == 200, reissued.text
        assert client.get("/api/v1/inbox", headers=bearer).status_code == 401
        assert (
            client.get(
                "/api/v1/inbox",
                headers={"Authorization": f"Bearer {reissued.json()['access_token']}"},
            ).status_code
            == 200
        )

    with database.session_factory() as session:
        from agentpost.identity.models import Agent
        from agentpost.onboarding.models import ConnectorInstance

        assert session.scalar(select(func.count()).select_from(Agent)) == 1
        connectors = session.scalars(select(ConnectorInstance)).all()
        assert len(connectors) == 2
        assert {connector.connector_type for connector in connectors} == {"manus"}
        assert sum(connector.status == "active" for connector in connectors) == 1
        active_connector = next(
            connector for connector in connectors if connector.status == "active"
        )
        assert active_connector.last_heartbeat_at is not None
        assert active_connector.health_status == "healthy"


def test_remote_mcp_oauth_is_off_by_default(client: TestClient) -> None:
    response = client.post(
        "/oauth/device_authorization",
        data={"client_id": OFFICIAL_REMOTE_MCP_CLIENT_ID, "scope": "agentpost.messaging"},
    )
    assert response.status_code == 404
    assert response.json()["error"] == "temporarily_unavailable"


def test_connector_migration_revokes_remote_oauth_family(
    settings: Settings,
    database: Database,
) -> None:
    runtime = _settings(settings)
    with TestClient(create_app(settings=runtime, database=database)) as client:
        human = _human(client)
        device = _device_authorization(client)
        decision = _authorize_device(client, human=human, device=device)
        agent_id = decision["pairing"]["agent"]["id"]
        token = _exchange(client, device["device_code"]).json()
        bearer = {"Authorization": f"Bearer {token['access_token']}"}
        assert client.get("/api/v1/inbox", headers=bearer).status_code == 200

        replacement = client.post(
            "/api/v1/connect/pairings",
            json={"connector_type": "codex", "display_name": "Replacement Codex"},
        ).json()
        confirmation = client.post(
            f"/api/v1/orbit/pairings/{replacement['pairing_id']}/confirmation",
            headers={
                "Authorization": f"Bearer {human['access_key']}",
                "X-CSRF-Token": human["csrf_token"],
            },
            json={"intent": "approve", "user_code": replacement["user_code"]},
        )
        assert confirmation.status_code == 200, confirmation.text
        migrated = client.post(
            f"/api/v1/orbit/pairings/{replacement['pairing_id']}/decision",
            headers={
                "X-CSRF-Token": human["csrf_token"],
                "X-Human-Confirmation": confirmation.json()["confirmation_token"],
                "Idempotency-Key": "replace-remote-mcp-connector",
            },
            json={"decision": "approved", "existing_agent_id": agent_id},
        )
        assert migrated.status_code == 200, migrated.text
        assert migrated.json()["pairing"]["agent"]["id"] == agent_id
        assert client.get("/api/v1/inbox", headers=bearer).status_code == 401
        refreshed = client.post(
            "/oauth/token",
            data={
                "grant_type": "refresh_token",
                "client_id": OFFICIAL_REMOTE_MCP_CLIENT_ID,
                "refresh_token": token["refresh_token"],
            },
        )
        assert refreshed.status_code == 400
        assert refreshed.json()["error"] == "invalid_grant"
