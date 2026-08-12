from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from agentpost.config import Settings
from agentpost.db import Database
from agentpost.identity.api_keys import digest_api_key
from agentpost.identity.models import Agent, AgentApiKey
from agentpost.main import create_app


def register(
    client: TestClient,
    address: str,
    *,
    headers: dict[str, str] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "address": address,
        "display_name": address.partition("@")[0].title(),
        "description": "A test agent",
        "capabilities": ["financial-research"],
    }
    payload.update(overrides)
    response = client.post("/api/v1/agents", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def bearer(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


def test_registration_returns_key_once_and_public_lookup_is_safe(
    client: TestClient,
    database: Database,
    settings: Settings,
) -> None:
    registration = register(
        client,
        "Alice@Agents.Local",
        capabilities=["Financial-Research", "financial-research", "Web-Search"],
    )
    profile = registration["agent"]
    api_key = registration["api_key"]

    assert profile["address"] == "alice@agents.local"
    assert profile["domain"] == "agents.local"
    assert profile["status"] == "active"
    assert profile["capabilities"] == ["financial-research", "web-search"]
    assert api_key.startswith("agt_")
    assert registration["api_key_prefix"] == api_key[:16]

    with database.session_factory() as session:
        agent = session.scalar(select(Agent).where(Agent.address == "alice@agents.local"))
        credential = session.scalar(select(AgentApiKey))
        assert agent is not None
        assert credential is not None
        assert credential.key_digest == digest_api_key(api_key, settings.api_key_pepper)
        assert credential.key_digest != api_key
        assert api_key not in repr(credential.__dict__)

    by_id = client.get(f"/api/v1/agents/{profile['id']}")
    by_address = client.get("/api/v1/agents/by-address/ALICE@AGENTS.LOCAL")
    assert by_id.status_code == 200
    assert by_address.status_code == 200
    for result in (by_id.json(), by_address.json()):
        assert result == profile
        assert "api_key" not in result
        assert "key_digest" not in result
        assert "key_prefix" not in result


def test_registration_rejects_duplicate_canonical_address(client: TestClient) -> None:
    register(client, "alice@agents.local")

    response = client.post(
        "/api/v1/agents",
        json={"address": "ALICE@AGENTS.LOCAL", "display_name": "Another Alice"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ADDRESS_ALREADY_REGISTERED"


def test_registration_token_is_required_when_configured(
    settings: Settings,
    database: Database,
) -> None:
    protected_settings = Settings(
        environment="test",
        database_url=settings.database_url,
        storage_path=settings.storage_path,
        api_key_pepper="test-pepper",
        cursor_secret="test-cursor-secret",
        registration_token="register-me",
        log_level="WARNING",
    )
    app = create_app(settings=protected_settings, database=database)
    with TestClient(app) as protected_client:
        missing = protected_client.post(
            "/api/v1/agents", json={"address": "alice@agents.local"}
        )
        wrong = protected_client.post(
            "/api/v1/agents",
            json={"address": "alice@agents.local"},
            headers={"X-Registration-Token": "wrong"},
        )
        created = protected_client.post(
            "/api/v1/agents",
            json={"address": "alice@agents.local"},
            headers={"X-Registration-Token": "register-me"},
        )

    assert missing.status_code == 403
    assert wrong.status_code == 403
    assert created.status_code == 201


def test_authenticated_agent_can_only_patch_its_safe_profile_fields(
    client: TestClient,
) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")

    updated = client.patch(
        f"/api/v1/agents/{alice['agent']['id']}",
        headers=bearer(alice["api_key"]),
        json={
            "display_name": "Alice Research",
            "description": None,
            "capabilities": ["Banking-Research", "banking-research"],
            "endpoint": "https://alice.example/agentpost",
        },
    )

    assert updated.status_code == 200
    assert updated.json()["display_name"] == "Alice Research"
    assert updated.json()["description"] is None
    assert updated.json()["capabilities"] == ["banking-research"]

    forbidden_other = client.patch(
        f"/api/v1/agents/{bob['agent']['id']}",
        headers=bearer(alice["api_key"]),
        json={"display_name": "Impersonated Bob"},
    )
    assert forbidden_other.status_code == 403


@pytest.mark.parametrize("field", ["id", "address", "status", "api_key", "public_key"])
def test_patch_forbids_identity_and_credential_fields(client: TestClient, field: str) -> None:
    alice = register(client, "alice@agents.local")
    values = {
        "id": "b96da13f-6bba-4dc9-bda9-c23aac887c4a",
        "address": "mallory@agents.local",
        "status": "disabled",
        "api_key": "agt_replacement",
        "public_key": "replacement-key",
    }

    response = client.patch(
        f"/api/v1/agents/{alice['agent']['id']}",
        headers=bearer(alice["api_key"]),
        json={field: values[field]},
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["type"] == "extra_forbidden"


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Basic abc"},
        {"Authorization": "Bearer not-an-agent-key"},
        {"Authorization": "Bearer agt_invalid-but-long-enough"},
    ],
)
def test_missing_or_invalid_credentials_return_401(
    client: TestClient, headers: dict[str, str]
) -> None:
    alice = register(client, "alice@agents.local")

    response = client.patch(
        f"/api/v1/agents/{alice['agent']['id']}",
        headers=headers,
        json={"display_name": "Nope"},
    )

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "INVALID_API_KEY"


def test_revoked_api_key_returns_401(client: TestClient, database: Database) -> None:
    alice = register(client, "alice@agents.local")
    with database.session_factory() as session:
        credential = session.scalar(select(AgentApiKey))
        assert credential is not None
        credential.revoked_at = datetime.now(UTC)
        session.commit()

    response = client.patch(
        f"/api/v1/agents/{alice['agent']['id']}",
        headers=bearer(alice["api_key"]),
        json={"display_name": "Nope"},
    )

    assert response.status_code == 401


def test_create_and_update_payloads_forbid_unknown_fields(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/agents",
        json={"address": "alice@agents.local", "unexpected": True},
    )

    assert create_response.status_code == 422
    assert create_response.json()["error"]["details"][0]["type"] == "extra_forbidden"


def test_unknown_agent_lookups_return_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/agents/2e78d3be-fc9a-4cb3-89ef-404b8768d3bd")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "AGENT_NOT_FOUND"
