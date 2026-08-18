from __future__ import annotations

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
            "Idempotency-Key": "oauth-device-owner-decision",
        },
        json={
            "decision": "approved",
            "local_agent_id": "remote-mcp-agent",
            "display_name": "Remote MCP Agent",
        },
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
