from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from agentpost.control.models import (
    AgentOwnership,
    HumanUser,
    OrganizationAgent,
    OrganizationMembership,
)
from agentpost.identity.models import Agent


@dataclass(frozen=True)
class OrganizationParticipant:
    agent: Agent
    human_user_id: UUID | None
    participation_source: Literal["assigned", "default"]


def effective_organization_participants(
    session: Session,
    *,
    organization_id: UUID,
) -> list[OrganizationParticipant]:
    """Return the Agents that can participate in an organization channel.

    Explicit assignments keep their existing single-organization ownership rule. For an
    owner/admin/member who has no explicitly assigned owned Agent in this organization,
    their active default Agent participates implicitly. This lets one Human use a default
    Agent in multiple organizations without silently moving the explicit assignment.
    """

    explicit_rows = session.execute(
        select(Agent, AgentOwnership.human_user_id)
        .join(OrganizationAgent, OrganizationAgent.agent_id == Agent.id)
        .outerjoin(AgentOwnership, AgentOwnership.agent_id == Agent.id)
        .where(
            OrganizationAgent.organization_id == organization_id,
            Agent.status == "active",
        )
        .order_by(Agent.address)
    ).all()
    participants: dict[UUID, OrganizationParticipant] = {}
    humans_with_assigned_agents: set[UUID] = set()
    for agent, human_user_id in explicit_rows:
        participants[agent.id] = OrganizationParticipant(
            agent=agent,
            human_user_id=human_user_id,
            participation_source="assigned",
        )
        if human_user_id is not None:
            humans_with_assigned_agents.add(human_user_id)

    default_rows = session.execute(
        select(HumanUser.id, Agent)
        .join(
            OrganizationMembership,
            OrganizationMembership.human_user_id == HumanUser.id,
        )
        .join(Agent, Agent.id == HumanUser.default_agent_id)
        .join(
            AgentOwnership,
            and_(
                AgentOwnership.agent_id == Agent.id,
                AgentOwnership.human_user_id == HumanUser.id,
            ),
        )
        .where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.role.in_(("owner", "admin", "member")),
            HumanUser.status == "active",
            Agent.status == "active",
        )
        .order_by(HumanUser.username, Agent.address)
    ).all()
    for human_user_id, agent in default_rows:
        if human_user_id in humans_with_assigned_agents or agent.id in participants:
            continue
        participants[agent.id] = OrganizationParticipant(
            agent=agent,
            human_user_id=human_user_id,
            participation_source="default",
        )

    return sorted(participants.values(), key=lambda item: item.agent.address)
