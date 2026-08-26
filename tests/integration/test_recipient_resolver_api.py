from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from agentpost.control.models import (
    AgentOwnership,
    HumanUser,
    Organization,
    OrganizationAgent,
    OrganizationMembership,
)
from agentpost.db import Database
from agentpost.identity.models import Agent
from agentpost.onboarding.models import AgentConnectorBinding, ConnectorInstance


def _register(
    client: TestClient,
    address: str,
    *,
    display_name: str,
    handle: str | None = None,
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/agents",
        json={"address": address, "display_name": display_name, "handle": handle},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _bearer(registration: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {registration['api_key']}"}


def _resolve(
    client: TestClient,
    caller: dict[str, Any],
    query: str,
):
    return client.post(
        "/api/v1/directory/resolve",
        headers=_bearer(caller),
        json={"query": query},
    )


def _relationship_scope(
    database: Database,
    *,
    caller_address: str,
    target_address: str,
    owner_name: str,
    owner_email: str,
    organization_slug: str,
    organization_name: str,
    connector_type: str = "codex",
) -> None:
    with database.session_factory() as session:
        caller = session.scalar(select(Agent).where(Agent.address == caller_address))
        target = session.scalar(select(Agent).where(Agent.address == target_address))
        assert caller is not None
        assert target is not None

        caller_owner = session.scalar(
            select(HumanUser).where(HumanUser.email == "caller-owner@example.com")
        )
        if caller_owner is None:
            caller_owner = HumanUser(
                email="caller-owner@example.com",
                display_name="发送者",
                status="active",
            )
            session.add(caller_owner)
            session.flush()
            session.add(AgentOwnership(agent_id=caller.id, human_user_id=caller_owner.id))

        target_owner = session.scalar(select(HumanUser).where(HumanUser.email == owner_email))
        if target_owner is None:
            target_owner = HumanUser(
                email=owner_email,
                display_name=owner_name,
                status="active",
            )
            session.add(target_owner)
            session.flush()
        if session.get(AgentOwnership, target.id) is None:
            session.add(AgentOwnership(agent_id=target.id, human_user_id=target_owner.id))

        organization = session.scalar(
            select(Organization).where(Organization.slug == organization_slug)
        )
        if organization is None:
            organization = Organization(
                slug=organization_slug,
                name=organization_name,
                status="active",
            )
            session.add(organization)
            session.flush()
            session.add(
                OrganizationMembership(
                    organization_id=organization.id,
                    human_user_id=caller_owner.id,
                    role="member",
                )
            )
        if session.get(OrganizationAgent, target.id) is None:
            session.add(
                OrganizationAgent(
                    agent_id=target.id,
                    organization_id=organization.id,
                )
            )

        if session.get(AgentConnectorBinding, target.id) is None:
            connector = ConnectorInstance(
                connector_id=f"connector-{target.id}",
                agent_id=target.id,
                human_user_id=target_owner.id,
                connector_type=connector_type,
                display_name=f"{connector_type} connector",
                status="active",
                health_status="healthy",
            )
            session.add(connector)
            session.flush()
            session.add(
                AgentConnectorBinding(
                    agent_id=target.id,
                    connector_instance_id=connector.id,
                )
            )
        session.commit()


@pytest.mark.parametrize(
    "query",
    [
        "给张子良的 Codex 发一段星云驿开发进度",
        "把这份材料发给张子良的 Agent",
        "回复张子良的 Codex",
    ],
)
def test_human_name_and_agent_type_resolve_unique_codex_and_send(
    client: TestClient,
    database: Database,
    query: str,
) -> None:
    caller = _register(client, "caller@agentpost.me", display_name="Caller")
    target = _register(
        client,
        "codex-f26e6148ca9297e992243fce@agentpost.me",
        display_name="开发 Codex",
        handle="kcode",
    )
    _relationship_scope(
        database,
        caller_address=caller["agent"]["address"],
        target_address=target["agent"]["address"],
        owner_name="张子良",
        owner_email="ziliang@example.com",
        organization_slug="product",
        organization_name="产品组",
    )

    response = _resolve(client, caller, query)

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "resolved"
    assert result["match"]["agent_id"] == target["agent"]["id"]
    assert result["match"]["label"] == "张子良的 Codex"
    assert result["match"]["match_kind"] == "human_agent"
    assert result["security_label"] == "external_agent_content"
    sent = client.post(
        "/api/v1/messages",
        headers={
            **_bearer(caller),
            "Idempotency-Key": f"natural-recipient-{target['agent']['id']}-{len(query)}",
        },
        json={
            "to": [{"address": result["match"]["address"]}],
            "type": "message",
            "subject": "星云驿开发进度",
            "content": {"format": "text", "body": "这是一段星云驿开发进度。"},
        },
    )
    assert sent.status_code == 201, sent.text
    assert sent.json()["to"][0]["agent_id"] == target["agent"]["id"]


def test_natural_handle_and_legacy_address_resolve_same_agent(client: TestClient) -> None:
    caller = _register(client, "caller@agentpost.me", display_name="Caller")
    target = _register(
        client,
        "codex-f26e6148ca9297e992243fce@agentpost.me",
        display_name="开发 Codex",
        handle="kcode",
    )

    by_handle = _resolve(client, caller, "给 kcode 发消息")
    by_address = _resolve(client, caller, target["agent"]["address"])

    assert by_handle.status_code == 200
    assert by_address.status_code == 200
    assert by_handle.json()["match"]["agent_id"] == target["agent"]["id"]
    assert by_handle.json()["match"]["match_kind"] == "handle"
    assert by_address.json()["match"]["agent_id"] == target["agent"]["id"]
    assert by_address.json()["match"]["match_kind"] == "address"


@pytest.mark.parametrize(
    "query",
    [
        "020的 Codex",
        "给用户 020 的 codex 发信息",
        "用户 020 名下的 Codex Agent",
    ],
)
def test_human_constraint_wins_over_incidental_global_type_handle(
    client: TestClient,
    database: Database,
    query: str,
) -> None:
    caller = _register(
        client,
        "magent@agentpost.me",
        display_name="mars agent",
        handle="codex",
    )
    target = _register(
        client,
        "020-codex-001@agentpost.me",
        display_name="pa020",
        handle="pa020",
    )
    _relationship_scope(
        database,
        caller_address=caller["agent"]["address"],
        target_address=target["agent"]["address"],
        owner_name="020",
        owner_email="020@example.com",
        organization_slug="doubao-canary",
        organization_name="豆包联调",
    )

    response = _resolve(client, caller, query)
    by_unqualified_handle = _resolve(client, caller, "给 codex 发消息")

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "resolved"
    assert result["match"]["agent_id"] == target["agent"]["id"]
    assert result["match"]["label"] == "020的 Codex"
    assert result["match"]["match_kind"] == "human_agent"
    assert by_unqualified_handle.json()["match"]["agent_id"] == caller["agent"]["id"]
    assert by_unqualified_handle.json()["match"]["match_kind"] == "handle"


def test_unknown_human_constraint_does_not_fall_back_to_type_handle(
    client: TestClient,
) -> None:
    caller = _register(
        client,
        "magent@agentpost.me",
        display_name="mars agent",
        handle="codex",
    )

    response = _resolve(client, caller, "给用户 999 的 Codex 发信息")

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "not_found"
    assert result["match"] is None
    assert result["candidates"] == []


def test_human_constraint_can_select_one_owner_scoped_handle(
    client: TestClient,
    database: Database,
) -> None:
    caller = _register(client, "caller@agentpost.me", display_name="Caller")
    first = _register(
        client,
        "first-long-technical-address@agentpost.me",
        display_name="工作 Codex",
        handle="kcode",
    )
    second = _register(
        client,
        "second-long-technical-address@agentpost.me",
        display_name="研究 Codex",
        handle="research-agent",
    )
    for target in (first, second):
        _relationship_scope(
            database,
            caller_address=caller["agent"]["address"],
            target_address=target["agent"]["address"],
            owner_name="张子良",
            owner_email="ziliang@example.com",
            organization_slug="product",
            organization_name="产品组",
        )

    response = _resolve(client, caller, "给张子良的 kcode 发消息")

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "resolved"
    assert result["match"]["agent_id"] == first["agent"]["id"]
    assert result["match"]["match_kind"] == "human_agent"


def test_nonexistent_handle_is_not_synthesized_into_an_address(client: TestClient) -> None:
    caller = _register(client, "caller@agentpost.me", display_name="Caller")

    response = _resolve(client, caller, "给 does-not-exist 发消息")

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "not_found"
    assert result["match"] is None
    assert result["candidates"] == []
    assert "does-not-exist@agentpost.me" not in response.text


def test_same_human_with_multiple_codex_agents_asks_once_with_short_labels(
    client: TestClient,
    database: Database,
) -> None:
    caller = _register(client, "caller@agentpost.me", display_name="Caller")
    first = _register(
        client,
        "first-long-technical-address@agentpost.me",
        display_name="工作 Codex",
        handle="kcode",
    )
    second = _register(
        client,
        "second-long-technical-address@agentpost.me",
        display_name="研究 Codex",
        handle="research-agent",
    )
    for target in (first, second):
        _relationship_scope(
            database,
            caller_address=caller["agent"]["address"],
            target_address=target["agent"]["address"],
            owner_name="张子良",
            owner_email="ziliang@example.com",
            organization_slug="product",
            organization_name="产品组",
        )

    response = _resolve(client, caller, "把报告发给张子良的 Codex")

    result = response.json()
    assert result["status"] == "needs_clarification"
    assert result["total_candidates"] == 2
    assert [item["label"] for item in result["candidates"]] == [
        "张子良的 Codex（kcode）",
        "张子良的 Codex（research-agent）",
    ]


def test_same_human_display_name_is_distinguished_by_shared_organization(
    client: TestClient,
    database: Database,
) -> None:
    caller = _register(client, "caller@agentpost.me", display_name="Caller")
    first = _register(client, "first@agentpost.me", display_name="Codex A", handle="first-code")
    second = _register(
        client,
        "second@agentpost.me",
        display_name="Codex B",
        handle="second-code",
    )
    _relationship_scope(
        database,
        caller_address=caller["agent"]["address"],
        target_address=first["agent"]["address"],
        owner_name="张子良",
        owner_email="first-ziliang@example.com",
        organization_slug="research-one",
        organization_name="研究一部",
    )
    _relationship_scope(
        database,
        caller_address=caller["agent"]["address"],
        target_address=second["agent"]["address"],
        owner_name="张子良",
        owner_email="second-ziliang@example.com",
        organization_slug="research-two",
        organization_name="研究二部",
    )

    response = _resolve(client, caller, "给张子良的 Codex 发消息")

    result = response.json()
    assert result["status"] == "needs_clarification"
    assert [item["label"] for item in result["candidates"]] == [
        "张子良（研究一部）的 Codex",
        "张子良（研究二部）的 Codex",
    ]
    assert all("@" not in item["label"] for item in result["candidates"])


def test_human_name_lookup_does_not_enumerate_unrelated_people(
    client: TestClient,
    database: Database,
) -> None:
    caller = _register(client, "caller@agentpost.me", display_name="Caller")
    target = _register(
        client,
        "private-ziliang@agentpost.me",
        display_name="Private Codex",
        handle="private-code",
    )
    with database.session_factory() as session:
        agent = session.scalar(select(Agent).where(Agent.address == target["agent"]["address"]))
        assert agent is not None
        owner = HumanUser(
            email="private-ziliang@example.com",
            display_name="张子良",
            status="active",
        )
        session.add(owner)
        session.flush()
        session.add(AgentOwnership(agent_id=agent.id, human_user_id=owner.id))
        session.commit()

    by_human = _resolve(client, caller, "给张子良的 Codex 发消息")
    by_explicit_handle = _resolve(client, caller, "给 private-code 发消息")

    assert by_human.json()["status"] == "not_found"
    assert by_explicit_handle.json()["status"] == "resolved"
    assert by_explicit_handle.json()["match"]["owner_display_name"] is None
