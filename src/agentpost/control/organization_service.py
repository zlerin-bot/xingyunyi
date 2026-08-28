from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agentpost.control.models import (
    AgentOwnership,
    HumanUser,
    Organization,
    OrganizationAgent,
    OrganizationMembership,
)
from agentpost.control.schemas import (
    OrbitOrganization,
    OrganizationAgentResponse,
    OrganizationCreate,
    OrganizationMemberAgentResponse,
    OrganizationMembershipResponse,
    OrganizationResponse,
)
from agentpost.identity.models import Agent, utc_now
from agentpost.messaging.models import AuditLog


class OrganizationSlugAlreadyRegisteredError(Exception):
    pass


class OrganizationNotFoundError(Exception):
    pass


class OrganizationMembershipNotFoundError(Exception):
    pass


class OrganizationAgentNotFoundError(Exception):
    pass


class OrganizationAgentAlreadyAssignedError(Exception):
    pass


@dataclass(frozen=True)
class OrganizationAgentAccess:
    agent: Agent
    organization: Organization
    membership_role: str
    granted_at: datetime


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _organization_counts(session: Session, organization_id: UUID) -> tuple[int, int]:
    member_count = session.scalar(
        select(func.count(OrganizationMembership.id)).where(
            OrganizationMembership.organization_id == organization_id
        )
    )
    agent_count = session.scalar(
        select(func.count(OrganizationAgent.agent_id)).where(
            OrganizationAgent.organization_id == organization_id
        )
    )
    return int(member_count or 0), int(agent_count or 0)


def organization_response(session: Session, organization: Organization) -> OrganizationResponse:
    member_count, agent_count = _organization_counts(session, organization.id)
    return OrganizationResponse(
        id=organization.id,
        slug=organization.slug,
        name=organization.name,
        description=organization.description,
        status=organization.status,
        member_count=member_count,
        agent_count=agent_count,
        created_at=_as_utc(organization.created_at),
        updated_at=_as_utc(organization.updated_at),
    )


def create_organization(
    session: Session,
    payload: OrganizationCreate,
    *,
    request_id: str,
) -> OrganizationResponse:
    if session.scalar(select(Organization.id).where(Organization.slug == payload.slug)) is not None:
        raise OrganizationSlugAlreadyRegisteredError(payload.slug)
    now = utc_now()
    organization = Organization(
        slug=payload.slug,
        name=payload.name,
        description=payload.description,
        status="active",
        created_at=now,
        updated_at=now,
    )
    session.add(organization)
    try:
        session.flush()
        session.add(
            AuditLog(
                actor_agent_id=None,
                action="control.organization_created",
                target_type="organization",
                target_id=str(organization.id),
                outcome="success",
                request_id=request_id,
                audit_metadata={"slug": organization.slug},
                created_at=now,
            )
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise OrganizationSlugAlreadyRegisteredError(payload.slug) from exc
    return organization_response(session, organization)


def list_organizations(session: Session, *, limit: int) -> list[OrganizationResponse]:
    organizations = session.scalars(
        select(Organization).order_by(Organization.slug).limit(limit)
    ).all()
    return [organization_response(session, organization) for organization in organizations]


def list_organization_memberships(
    session: Session,
    *,
    organization_id: UUID,
    limit: int,
) -> list[OrganizationMembershipResponse]:
    organization = session.get(Organization, organization_id)
    if organization is None:
        raise OrganizationNotFoundError(str(organization_id))
    rows = session.execute(
        select(OrganizationMembership, HumanUser)
        .join(HumanUser, HumanUser.id == OrganizationMembership.human_user_id)
        .where(OrganizationMembership.organization_id == organization.id)
        .order_by(HumanUser.email)
        .limit(limit)
    ).all()
    agent_rows = session.execute(
        select(AgentOwnership.human_user_id, Agent)
        .join(OrganizationAgent, OrganizationAgent.agent_id == AgentOwnership.agent_id)
        .join(Agent, Agent.id == AgentOwnership.agent_id)
        .where(OrganizationAgent.organization_id == organization.id)
        .order_by(Agent.handle, Agent.address)
    ).all()
    agents_by_human: dict[UUID, list[OrganizationMemberAgentResponse]] = {}
    for human_user_id, agent in agent_rows:
        agents_by_human.setdefault(human_user_id, []).append(
            OrganizationMemberAgentResponse(
                agent_id=agent.id,
                address=agent.address,
                handle=agent.handle,
                display_name=agent.display_name,
            )
        )
    return [
        OrganizationMembershipResponse(
            organization_id=organization.id,
            human_user_id=user.id,
            human_email=user.email,
            human_username=user.username,
            human_display_name=user.display_name,
            role=membership.role,
            agents=agents_by_human.get(user.id, []),
            created_at=_as_utc(membership.created_at),
            updated_at=_as_utc(membership.updated_at),
        )
        for membership, user in rows
    ]


def list_organization_agents(
    session: Session,
    *,
    organization_id: UUID,
    limit: int,
) -> list[OrganizationAgentResponse]:
    organization = session.get(Organization, organization_id)
    if organization is None:
        raise OrganizationNotFoundError(str(organization_id))
    rows = session.execute(
        select(OrganizationAgent, Agent)
        .join(Agent, Agent.id == OrganizationAgent.agent_id)
        .where(OrganizationAgent.organization_id == organization.id)
        .order_by(Agent.address)
        .limit(limit)
    ).all()
    return [
        OrganizationAgentResponse(
            organization_id=organization.id,
            agent_id=agent.id,
            agent_address=agent.address,
            assigned_at=_as_utc(assignment.assigned_at),
        )
        for assignment, agent in rows
    ]


def _load_organization(session: Session, organization_id: UUID) -> Organization:
    organization = session.scalar(
        select(Organization).where(Organization.id == organization_id).with_for_update()
    )
    if organization is None:
        raise OrganizationNotFoundError(str(organization_id))
    return organization


def set_organization_membership(
    session: Session,
    *,
    organization_id: UUID,
    human_user_id: UUID,
    role: str,
    request_id: str,
) -> OrganizationMembershipResponse:
    organization = _load_organization(session, organization_id)
    user = session.get(HumanUser, human_user_id)
    if user is None:
        raise OrganizationNotFoundError(str(human_user_id))
    membership = session.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization.id,
            OrganizationMembership.human_user_id == user.id,
        )
    )
    now = utc_now()
    if membership is None:
        membership = OrganizationMembership(
            organization_id=organization.id,
            human_user_id=user.id,
            role=role,
            created_at=now,
            updated_at=now,
        )
        session.add(membership)
    else:
        membership.role = role
        membership.updated_at = now
    session.flush()
    session.add(
        AuditLog(
            actor_agent_id=None,
            action="control.organization_membership_set",
            target_type="organization_membership",
            target_id=str(membership.id),
            outcome="success",
            request_id=request_id,
            audit_metadata={
                "organization_id": str(organization.id),
                "human_user_id": str(user.id),
                "role": role,
            },
            created_at=now,
        )
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise OrganizationNotFoundError(str(organization_id)) from exc
    return OrganizationMembershipResponse(
        organization_id=organization.id,
        human_user_id=user.id,
        human_email=user.email,
        human_username=user.username,
        human_display_name=user.display_name,
        role=membership.role,
        created_at=_as_utc(membership.created_at),
        updated_at=_as_utc(membership.updated_at),
    )


def remove_organization_membership(
    session: Session,
    *,
    organization_id: UUID,
    human_user_id: UUID,
    request_id: str,
) -> None:
    _load_organization(session, organization_id)
    membership = session.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.human_user_id == human_user_id,
        )
    )
    if membership is None:
        session.rollback()
        raise OrganizationMembershipNotFoundError(str(human_user_id))
    session.delete(membership)
    session.add(
        AuditLog(
            actor_agent_id=None,
            action="control.organization_membership_removed",
            target_type="organization_membership",
            target_id=str(membership.id),
            outcome="success",
            request_id=request_id,
            audit_metadata={
                "organization_id": str(organization_id),
                "human_user_id": str(human_user_id),
            },
            created_at=utc_now(),
        )
    )
    session.commit()


def assign_agent_to_organization(
    session: Session,
    *,
    organization_id: UUID,
    agent_id: UUID,
    request_id: str,
) -> OrganizationAgentResponse:
    organization = _load_organization(session, organization_id)
    agent = session.scalar(select(Agent).where(Agent.id == agent_id).with_for_update())
    if agent is None:
        raise OrganizationNotFoundError(str(agent_id))
    assignment = session.get(OrganizationAgent, agent.id)
    if assignment is not None and assignment.organization_id != organization.id:
        session.rollback()
        raise OrganizationAgentAlreadyAssignedError(str(agent.id))
    now = utc_now()
    if assignment is None:
        assignment = OrganizationAgent(
            agent_id=agent.id,
            organization_id=organization.id,
            assigned_at=now,
        )
        session.add(assignment)
        session.add(
            AuditLog(
                actor_agent_id=None,
                action="control.organization_agent_assigned",
                target_type="agent",
                target_id=str(agent.id),
                outcome="success",
                request_id=request_id,
                audit_metadata={"organization_id": str(organization.id)},
                created_at=now,
            )
        )
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise OrganizationAgentAlreadyAssignedError(str(agent.id)) from exc
    return OrganizationAgentResponse(
        organization_id=organization.id,
        agent_id=agent.id,
        agent_address=agent.address,
        assigned_at=_as_utc(assignment.assigned_at),
    )


def remove_agent_from_organization(
    session: Session,
    *,
    organization_id: UUID,
    agent_id: UUID,
    request_id: str,
) -> None:
    _load_organization(session, organization_id)
    assignment = session.get(OrganizationAgent, agent_id)
    if assignment is None or assignment.organization_id != organization_id:
        session.rollback()
        raise OrganizationAgentNotFoundError(str(agent_id))
    session.delete(assignment)
    session.add(
        AuditLog(
            actor_agent_id=None,
            action="control.organization_agent_removed",
            target_type="agent",
            target_id=str(agent_id),
            outcome="success",
            request_id=request_id,
            audit_metadata={"organization_id": str(organization_id)},
            created_at=utc_now(),
        )
    )
    session.commit()


def list_organization_agent_access(
    session: Session,
    user: HumanUser,
) -> list[OrganizationAgentAccess]:
    rows = session.execute(
        select(Agent, Organization, OrganizationMembership.role, OrganizationAgent.assigned_at)
        .join(OrganizationAgent, OrganizationAgent.agent_id == Agent.id)
        .join(Organization, Organization.id == OrganizationAgent.organization_id)
        .join(
            OrganizationMembership,
            OrganizationMembership.organization_id == Organization.id,
        )
        .where(
            OrganizationMembership.human_user_id == user.id,
            Organization.status == "active",
        )
        .order_by(Agent.address)
    ).all()
    return [
        OrganizationAgentAccess(
            agent=agent,
            organization=organization,
            membership_role=role,
            granted_at=assigned_at,
        )
        for agent, organization, role, assigned_at in rows
    ]


def list_orbit_organizations(session: Session, user: HumanUser) -> list[OrbitOrganization]:
    rows = session.execute(
        select(Organization, OrganizationMembership.role)
        .join(
            OrganizationMembership,
            OrganizationMembership.organization_id == Organization.id,
        )
        .where(
            OrganizationMembership.human_user_id == user.id,
            Organization.status == "active",
        )
        .order_by(Organization.name, Organization.slug)
    ).all()
    results: list[OrbitOrganization] = []
    for organization, role in rows:
        member_count, agent_count = _organization_counts(session, organization.id)
        results.append(
            OrbitOrganization(
                id=organization.id,
                slug=organization.slug,
                name=organization.name,
                description=organization.description,
                membership_role=role,
                member_count=member_count,
                agent_count=agent_count,
            )
        )
    return results
