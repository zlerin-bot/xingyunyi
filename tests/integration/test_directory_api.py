from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from agentpost.api.routes.directory import router as directory_router
from agentpost.config import Settings
from agentpost.db import Database
from agentpost.directory.schemas import DirectoryAgentProfile
from agentpost.identity.models import Agent
from agentpost.main import create_app


@pytest.fixture
def directory_client(settings: Settings, database: Database) -> Iterator[TestClient]:
    app = create_app(settings=settings, database=database)
    if not any(getattr(route, "path", None) == "/api/v1/directory/search" for route in app.routes):
        app.include_router(directory_router)
    with TestClient(app) as test_client:
        yield test_client


def register(
    client: TestClient,
    address: str,
    *,
    display_name: str | None = None,
    description: str | None = "Directory test profile",
    capabilities: list[str] | None = None,
    public_key: str | None = None,
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/agents",
        json={
            "address": address,
            "display_name": display_name or address.partition("@")[0].title(),
            "description": description,
            "capabilities": capabilities or [],
            "public_key": public_key,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def bearer(registration: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {registration['api_key']}"}


def search(
    client: TestClient,
    registration: dict[str, Any],
    **params: Any,
):
    return client.get(
        "/api/v1/directory/search",
        headers=bearer(registration),
        params=params,
    )


def contact(
    client: TestClient,
    sender: dict[str, Any],
    recipient: dict[str, Any],
    suffix: str,
) -> None:
    response = client.post(
        "/api/v1/messages",
        headers={
            **bearer(sender),
            "Idempotency-Key": f"directory-contact-{suffix}",
        },
        json={
            "to": [{"address": recipient["agent"]["address"]}],
            "type": "message",
            "subject": "建立联系人关系",
            "content": {"format": "text", "body": "你好"},
        },
    )
    assert response.status_code == 201, response.text


def addresses(response: Any) -> list[str]:
    assert response.status_code == 200, response.text
    return [item["address"] for item in response.json()["items"]]


def test_q_searches_address_name_and_description_case_insensitively(
    directory_client: TestClient,
) -> None:
    caller = register(directory_client, "caller@agents.local")
    address_match = register(
        directory_client,
        "bank-address@agents.local",
        display_name="Address match",
        description=None,
    )
    display_match = register(
        directory_client,
        "display@agents.local",
        display_name="Institutional BANK Desk",
        description=None,
    )
    description_match = register(
        directory_client,
        "description@agents.local",
        display_name="Description match",
        description="Researches regional Bank balance sheets",
    )
    register(
        directory_client,
        "unrelated@agents.local",
        display_name="Unrelated",
        description=None,
    )
    contact(directory_client, caller, address_match, "q-address")
    contact(directory_client, caller, display_match, "q-display")
    contact(directory_client, description_match, caller, "q-description-inbound")

    response = search(directory_client, caller, q="BaNk")

    assert addresses(response) == [
        "bank-address@agents.local",
        "description@agents.local",
        "display@agents.local",
    ]


def test_capability_is_normalized_and_matches_exactly(
    directory_client: TestClient,
) -> None:
    caller = register(directory_client, "caller@agents.local")
    alpha = register(
        directory_client,
        "alpha@agents.local",
        capabilities=["Financial-Research"],
    )
    beta = register(
        directory_client,
        "beta@agents.local",
        capabilities=["financial-research-plus"],
    )
    gamma = register(
        directory_client,
        "gamma@agents.local",
        capabilities=["financial-research", "web-search"],
    )
    contact(directory_client, caller, alpha, "cap-alpha")
    contact(directory_client, caller, beta, "cap-beta")
    contact(directory_client, caller, gamma, "cap-gamma")

    response = search(
        directory_client,
        caller,
        capability="  FINANCIAL-RESEARCH  ",
    )

    assert addresses(response) == ["alpha@agents.local", "gamma@agents.local"]


def test_q_and_capability_filters_are_combined(directory_client: TestClient) -> None:
    caller = register(directory_client, "caller@agents.local")
    bank_finance = register(
        directory_client,
        "bank-finance@agents.local",
        capabilities=["financial-research"],
    )
    bank_web = register(
        directory_client,
        "bank-web@agents.local",
        capabilities=["web-search"],
    )
    technology = register(
        directory_client,
        "technology@agents.local",
        display_name="Technology analyst",
        capabilities=["financial-research"],
    )
    contact(directory_client, caller, bank_finance, "combined-finance")
    contact(directory_client, caller, bank_web, "combined-web")
    contact(directory_client, caller, technology, "combined-tech")

    response = search(
        directory_client,
        caller,
        q="bank",
        capability="financial-research",
    )

    assert addresses(response) == ["bank-finance@agents.local"]


def test_directory_only_returns_active_agents(
    directory_client: TestClient,
    database: Database,
) -> None:
    caller = register(directory_client, "caller@agents.local")
    active = register(directory_client, "active-match@agents.local")
    disabled_registration = register(directory_client, "disabled-match@agents.local")
    suspended_registration = register(directory_client, "suspended-match@agents.local")
    contact(directory_client, caller, active, "status-active")
    contact(directory_client, caller, disabled_registration, "status-disabled")
    contact(directory_client, caller, suspended_registration, "status-suspended")
    with database.session_factory() as session:
        disabled = session.scalar(
            select(Agent).where(Agent.address == "disabled-match@agents.local")
        )
        suspended = session.scalar(
            select(Agent).where(Agent.address == "suspended-match@agents.local")
        )
        assert disabled is not None
        assert suspended is not None
        disabled.status = "disabled"
        suspended.status = "suspended"
        session.commit()

    response = search(directory_client, caller, q="match")

    assert addresses(response) == ["active-match@agents.local"]


def test_directory_requires_agent_authentication(directory_client: TestClient) -> None:
    missing = directory_client.get("/api/v1/directory/search", params={"q": "bank"})
    invalid = directory_client.get(
        "/api/v1/directory/search",
        params={"q": "bank"},
        headers={"Authorization": "Bearer agt_invalid-but-long-enough"},
    )

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert missing.json()["error"]["code"] == "INVALID_API_KEY"
    assert invalid.json()["error"]["code"] == "INVALID_API_KEY"


def test_response_has_only_safe_strict_profile_fields(
    directory_client: TestClient,
    database: Database,
) -> None:
    caller = register(directory_client, "caller@agents.local")
    target = register(
        directory_client,
        "safe-target@agents.local",
        capabilities=["financial-research"],
        public_key="public-key-material",
    )
    contact(directory_client, caller, target, "safe-profile")
    with database.session_factory() as session:
        agent = session.scalar(select(Agent).where(Agent.address == "safe-target@agents.local"))
        assert agent is not None
        agent.owner_id = "private-owner-id"
        session.commit()

    response = search(directory_client, caller, q="safe-target")

    assert response.status_code == 200, response.text
    item = response.json()["items"][0]
    assert set(item) == set(DirectoryAgentProfile.model_fields)
    assert item["capability_verification"] == "self_declared"
    assert item["public_key"] == "public-key-material"
    assert "owner_id" not in item
    assert "api_key" not in item
    assert "key_digest" not in item
    assert target["api_key"] not in response.text


def test_results_are_address_sorted_and_honor_limit(directory_client: TestClient) -> None:
    caller = register(directory_client, "caller@agents.local")
    targets = [
        register(directory_client, address)
        for address in (
            "zulu-common@agents.local",
            "alpha-common@agents.local",
            "beta-common@agents.local",
        )
    ]
    for index, target in enumerate(targets):
        contact(directory_client, caller, target, f"sort-{index}")

    response = search(directory_client, caller, q="common", limit=2)

    assert addresses(response) == [
        "alpha-common@agents.local",
        "beta-common@agents.local",
    ]


def test_like_metacharacters_are_literal_not_unrestricted_searches(
    directory_client: TestClient,
) -> None:
    caller = register(directory_client, "caller@agents.local")
    register(directory_client, "ordinary@agents.local")

    percent = search(directory_client, caller, q="%")
    underscore = search(directory_client, caller, q="_")

    assert addresses(percent) == []
    assert addresses(underscore) == []


def test_directory_does_not_list_agents_without_a_verified_relationship(
    directory_client: TestClient,
) -> None:
    caller = register(directory_client, "caller@agents.local")
    contacted = register(directory_client, "contacted-common@agents.local")
    register(directory_client, "unknown-common@agents.local")
    contact(directory_client, caller, contacted, "relationship-boundary")

    response = search(directory_client, caller, q="common")

    assert addresses(response) == ["contacted-common@agents.local"]


@pytest.mark.parametrize(
    ("params", "expected_code"),
    [
        ({}, "INVALID_DIRECTORY_FILTER"),
        ({"q": ""}, "INVALID_DIRECTORY_FILTER"),
        ({"q": "   "}, "INVALID_DIRECTORY_FILTER"),
        ({"capability": ""}, "INVALID_DIRECTORY_FILTER"),
        ({"capability": "   "}, "INVALID_DIRECTORY_FILTER"),
        ({"q": "x" * 201}, "SCHEMA_VALIDATION_FAILED"),
        ({"capability": "x" * 101}, "SCHEMA_VALIDATION_FAILED"),
        ({"q": "bank", "limit": 0}, "SCHEMA_VALIDATION_FAILED"),
        ({"q": "bank", "limit": 101}, "SCHEMA_VALIDATION_FAILED"),
    ],
)
def test_directory_rejects_unbounded_or_invalid_filters(
    directory_client: TestClient,
    params: dict[str, Any],
    expected_code: str,
) -> None:
    caller = register(directory_client, "caller@agents.local")

    response = search(directory_client, caller, **params)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == expected_code
