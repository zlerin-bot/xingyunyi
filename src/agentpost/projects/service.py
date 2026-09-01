from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from agentpost.control.human_security import add_human_action_audit
from agentpost.control.models import AgentOwnership, HumanUser
from agentpost.identity.models import Agent, utc_now
from agentpost.messaging.models import Delivery, Message
from agentpost.projects.models import Project, ProjectActivity, ProjectMembership
from agentpost.projects.schemas import (
    FriendAgent,
    FriendResponse,
    ProjectActivityResponse,
    ProjectCreate,
    ProjectDetail,
    ProjectMember,
    ProjectSummary,
)


class ProjectNotFoundError(Exception):
    pass


class ProjectOwnerRequiredError(Exception):
    pass


class ProjectFriendRequiredError(Exception):
    pass


class ProjectMembershipConflictError(Exception):
    pass


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def list_friends(
    session: Session,
    *,
    user: HumanUser,
    query: str | None = None,
    limit: int = 100,
) -> list[FriendResponse]:
    """Return only Humans reached through verified Agent-to-Agent messages."""

    owned_agent_ids = list(
        session.scalars(
            select(AgentOwnership.agent_id).where(AgentOwnership.human_user_id == user.id)
        )
    )
    if not owned_agent_ids:
        return []

    latest_by_agent: dict[UUID, datetime] = {}
    outgoing = session.execute(
        select(Delivery.recipient_agent_id, func.max(Message.created_at))
        .join(Message, Message.id == Delivery.message_id)
        .where(Message.sender_agent_id.in_(owned_agent_ids))
        .group_by(Delivery.recipient_agent_id)
    ).all()
    incoming = session.execute(
        select(Message.sender_agent_id, func.max(Message.created_at))
        .join(Delivery, Delivery.message_id == Message.id)
        .where(Delivery.recipient_agent_id.in_(owned_agent_ids))
        .group_by(Message.sender_agent_id)
    ).all()
    owned_agent_id_set = set(owned_agent_ids)
    for agent_id, contacted_at in [*outgoing, *incoming]:
        if agent_id in owned_agent_id_set or contacted_at is None:
            continue
        previous = latest_by_agent.get(agent_id)
        if previous is None or _as_utc(contacted_at) > _as_utc(previous):
            latest_by_agent[agent_id] = contacted_at
    if not latest_by_agent:
        return []

    rows = session.execute(
        select(AgentOwnership.agent_id, HumanUser, Agent)
        .join(HumanUser, HumanUser.id == AgentOwnership.human_user_id)
        .join(Agent, Agent.id == AgentOwnership.agent_id)
        .where(
            AgentOwnership.agent_id.in_(latest_by_agent),
            HumanUser.status == "active",
            HumanUser.id != user.id,
            Agent.status == "active",
        )
    ).all()
    normalized_query = query.strip().casefold() if query else ""
    grouped: dict[UUID, tuple[HumanUser, list[FriendAgent], datetime]] = {}
    for agent_id, candidate, agent in rows:
        if (
            normalized_query
            and normalized_query
            not in " ".join(
                [candidate.username, candidate.display_name, agent.display_name, agent.address]
            ).casefold()
        ):
            continue
        contacted_at = _as_utc(latest_by_agent[agent_id])
        friend_agent = FriendAgent(
            agent_id=agent.id,
            display_name=agent.display_name,
            address=agent.address,
            capabilities=[item for item in agent.capabilities if isinstance(item, str)],
            last_contact_at=contacted_at,
        )
        current = grouped.get(candidate.id)
        if current is None:
            grouped[candidate.id] = (candidate, [friend_agent], contacted_at)
        else:
            current[1].append(friend_agent)
            if contacted_at > current[2]:
                grouped[candidate.id] = (current[0], current[1], contacted_at)

    ordered = sorted(
        grouped.values(),
        key=lambda item: (-item[2].timestamp(), item[0].username),
    )[:limit]
    responses: list[FriendResponse] = []
    for candidate, agents, contacted_at in ordered:
        agents.sort(key=lambda item: (-item.last_contact_at.timestamp(), item.address))
        capabilities = sorted({capability for agent in agents for capability in agent.capabilities})
        responses.append(
            FriendResponse(
                human_user_id=candidate.id,
                username=candidate.username,
                display_name=candidate.display_name,
                last_contact_at=contacted_at,
                capabilities=capabilities,
                agents=agents,
            )
        )
    return responses


def _load_project_context(
    session: Session,
    *,
    project_id: UUID,
    user: HumanUser,
    lock: bool = False,
) -> tuple[Project, ProjectMembership]:
    statement = select(Project).where(Project.id == project_id)
    if lock:
        statement = statement.with_for_update()
    project = session.scalar(statement)
    membership = session.scalar(
        select(ProjectMembership).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.human_user_id == user.id,
            ProjectMembership.status.in_(["active", "invited"]),
        )
    )
    if project is None or membership is None:
        raise ProjectNotFoundError
    return project, membership


def _require_owner(project: Project, membership: ProjectMembership) -> None:
    if membership.role != "owner" or membership.status != "active":
        raise ProjectOwnerRequiredError
    if project.owner_human_user_id != membership.human_user_id:
        raise ProjectOwnerRequiredError


def _default_agent(
    session: Session,
    *,
    human: HumanUser,
    fallback_contact_at: datetime,
) -> FriendAgent | None:
    if human.default_agent_id is None:
        return None
    row = session.execute(
        select(Agent, AgentOwnership)
        .join(AgentOwnership, AgentOwnership.agent_id == Agent.id)
        .where(
            Agent.id == human.default_agent_id,
            Agent.status == "active",
            AgentOwnership.human_user_id == human.id,
        )
    ).first()
    if row is None:
        return None
    agent, _ = row
    return FriendAgent(
        agent_id=agent.id,
        display_name=agent.display_name,
        address=agent.address,
        capabilities=[item for item in agent.capabilities if isinstance(item, str)],
        last_contact_at=_as_utc(agent.last_seen_at or fallback_contact_at),
    )


def _member_rows(session: Session, project_id: UUID) -> list[tuple[ProjectMembership, HumanUser]]:
    return list(
        session.execute(
            select(ProjectMembership, HumanUser)
            .join(HumanUser, HumanUser.id == ProjectMembership.human_user_id)
            .where(
                ProjectMembership.project_id == project_id,
                ProjectMembership.status.in_(["active", "invited"]),
            )
            .order_by(ProjectMembership.role, ProjectMembership.invited_at, HumanUser.username)
        ).all()
    )


def _platform_activities(
    session: Session,
    *,
    project_id: UUID,
    humans: dict[UUID, HumanUser],
) -> list[ProjectActivityResponse]:
    rows = session.scalars(
        select(ProjectActivity)
        .where(ProjectActivity.project_id == project_id)
        .order_by(ProjectActivity.created_at.desc())
        .limit(100)
    ).all()
    return [
        ProjectActivityResponse(
            activity_id=str(activity.id),
            kind=activity.activity_type,  # type: ignore[arg-type]
            actor_human_user_id=activity.actor_human_user_id,
            actor_display_name=(
                humans[activity.actor_human_user_id].display_name
                if activity.actor_human_user_id in humans
                else None
            ),
            target_human_user_id=activity.target_human_user_id,
            target_display_name=(
                humans[activity.target_human_user_id].display_name
                if activity.target_human_user_id in humans
                else None
            ),
            security_label="platform_event",
            created_at=_as_utc(activity.created_at),
        )
        for activity in rows
    ]


def _agent_activities(
    session: Session,
    *,
    project_id: UUID,
    active_human_ids: set[UUID],
    humans: dict[UUID, HumanUser],
) -> list[ProjectActivityResponse]:
    ownership_rows = session.execute(
        select(AgentOwnership.agent_id, AgentOwnership.human_user_id).where(
            AgentOwnership.human_user_id.in_(active_human_ids)
        )
    ).all()
    human_by_agent = {agent_id: human_id for agent_id, human_id in ownership_rows}
    if not human_by_agent:
        return []
    agent_ids = list(human_by_agent)
    rows = session.execute(
        select(Message, Delivery, Agent)
        .join(Delivery, Delivery.message_id == Message.id)
        .join(Agent, Agent.id == Message.sender_agent_id)
        .where(
            or_(
                Message.sender_agent_id.in_(agent_ids),
                Delivery.recipient_agent_id.in_(agent_ids),
            )
        )
        .options(selectinload(Message.attachments))
        .order_by(Message.created_at.desc())
        .limit(500)
    ).all()
    activities: list[ProjectActivityResponse] = []
    for message, delivery, sender in rows:
        if str(message.message_metadata.get("project_id", "")) != str(project_id):
            continue
        sender_human_id = human_by_agent.get(message.sender_agent_id)
        recipient_human_id = human_by_agent.get(delivery.recipient_agent_id)
        if sender_human_id not in active_human_ids or recipient_human_id not in active_human_ids:
            continue
        is_delivery = message.message_type == "result" or bool(message.attachments)
        activities.append(
            ProjectActivityResponse(
                activity_id=f"message:{message.id}",
                kind="agent_delivery" if is_delivery else "agent_update",
                actor_human_user_id=sender_human_id,
                actor_display_name=humans[sender_human_id].display_name,
                target_human_user_id=recipient_human_id,
                target_display_name=humans[recipient_human_id].display_name,
                agent_id=sender.id,
                agent_display_name=sender.display_name,
                subject=message.subject,
                delivery_status=delivery.delivery_status,
                security_label="external_agent_content",
                created_at=_as_utc(message.created_at),
            )
        )
    return activities


def _project_detail(
    session: Session,
    *,
    project: Project,
    viewer_membership: ProjectMembership,
) -> ProjectDetail:
    rows = _member_rows(session, project.id)
    humans = {human.id: human for _, human in rows}
    owner = session.get(HumanUser, project.owner_human_user_id)
    if owner is None:
        raise ProjectNotFoundError
    humans[owner.id] = owner
    members = [
        ProjectMember(
            human_user_id=human.id,
            username=human.username,
            display_name=human.display_name,
            role=membership.role,  # type: ignore[arg-type]
            status=membership.status,  # type: ignore[arg-type]
            agent=(
                _default_agent(session, human=human, fallback_contact_at=membership.invited_at)
                if membership.status == "active"
                else None
            ),
            invited_at=_as_utc(membership.invited_at),
            joined_at=_as_utc(membership.joined_at) if membership.joined_at else None,
        )
        for membership, human in rows
    ]
    active_human_ids = {
        membership.human_user_id for membership, _ in rows if membership.status == "active"
    }
    activities = _platform_activities(session, project_id=project.id, humans=humans)
    activities.extend(
        _agent_activities(
            session,
            project_id=project.id,
            active_human_ids=active_human_ids,
            humans=humans,
        )
    )
    activities.sort(key=lambda item: item.created_at, reverse=True)
    return ProjectDetail(
        project_id=project.id,
        title=project.title,
        description=project.description,
        status=project.status,  # type: ignore[arg-type]
        due_at=_as_utc(project.due_at) if project.due_at else None,
        owner_human_user_id=owner.id,
        owner_display_name=owner.display_name,
        membership_role=viewer_membership.role,  # type: ignore[arg-type]
        membership_status=viewer_membership.status,  # type: ignore[arg-type]
        active_member_count=sum(item.status == "active" for item in members),
        invited_member_count=sum(item.status == "invited" for item in members),
        member_human_user_ids=[item.human_user_id for item in members],
        created_at=_as_utc(project.created_at),
        updated_at=_as_utc(project.updated_at),
        members=members,
        activities=activities[:100],
    )


def list_projects(session: Session, *, user: HumanUser, limit: int = 100) -> list[ProjectSummary]:
    rows = session.execute(
        select(Project, ProjectMembership)
        .join(ProjectMembership, ProjectMembership.project_id == Project.id)
        .where(
            ProjectMembership.human_user_id == user.id,
            ProjectMembership.status.in_(["active", "invited"]),
        )
        .order_by(Project.updated_at.desc(), Project.created_at.desc())
        .limit(limit)
    ).all()
    summaries: list[ProjectSummary] = []
    for project, membership in rows:
        detail = _project_detail(session, project=project, viewer_membership=membership)
        summaries.append(ProjectSummary(**detail.model_dump(exclude={"members", "activities"})))
    return summaries


def get_project(session: Session, *, user: HumanUser, project_id: UUID) -> ProjectDetail:
    project, membership = _load_project_context(session, project_id=project_id, user=user)
    return _project_detail(session, project=project, viewer_membership=membership)


def create_project(
    session: Session,
    *,
    user: HumanUser,
    payload: ProjectCreate,
    human_session_id: UUID | None,
    request_id: str,
) -> ProjectDetail:
    now = utc_now()
    project = Project(
        owner_human_user_id=user.id,
        title=payload.title,
        description=payload.description,
        due_at=payload.due_at,
        status="active",
        created_at=now,
        updated_at=now,
    )
    session.add(project)
    session.flush()
    membership = ProjectMembership(
        project_id=project.id,
        human_user_id=user.id,
        role="owner",
        status="active",
        invited_by_user_id=user.id,
        invited_at=now,
        joined_at=now,
        updated_at=now,
    )
    session.add(membership)
    session.add(
        ProjectActivity(
            project_id=project.id,
            activity_type="created",
            actor_human_user_id=user.id,
            target_human_user_id=None,
            created_at=now,
        )
    )
    add_human_action_audit(
        session,
        human_user_id=user.id,
        human_session_id=human_session_id,
        action="project.created",
        target_type="project",
        target_id=str(project.id),
        outcome="success",
        request_id=request_id,
    )
    session.commit()
    return _project_detail(session, project=project, viewer_membership=membership)


def list_project_invitation_candidates(
    session: Session,
    *,
    user: HumanUser,
    project_id: UUID,
    limit: int = 100,
) -> list[FriendResponse]:
    project, membership = _load_project_context(session, project_id=project_id, user=user)
    _require_owner(project, membership)
    existing_ids = set(
        session.scalars(
            select(ProjectMembership.human_user_id).where(
                ProjectMembership.project_id == project_id,
                ProjectMembership.status.in_(["active", "invited"]),
            )
        )
    )
    return [
        friend
        for friend in list_friends(session, user=user, limit=limit)
        if friend.human_user_id not in existing_ids
    ]


def invite_project_members(
    session: Session,
    *,
    user: HumanUser,
    project_id: UUID,
    human_user_ids: list[UUID],
    human_session_id: UUID | None,
    request_id: str,
) -> ProjectDetail:
    project, membership = _load_project_context(
        session, project_id=project_id, user=user, lock=True
    )
    _require_owner(project, membership)
    allowed_ids = {friend.human_user_id for friend in list_friends(session, user=user, limit=200)}
    if not set(human_user_ids).issubset(allowed_ids):
        raise ProjectFriendRequiredError
    existing_ids = set(
        session.scalars(
            select(ProjectMembership.human_user_id).where(
                ProjectMembership.project_id == project_id,
                ProjectMembership.status.in_(["active", "invited"]),
            )
        )
    )
    if existing_ids.intersection(human_user_ids):
        raise ProjectMembershipConflictError
    now = utc_now()
    for invitee_id in human_user_ids:
        existing = session.get(ProjectMembership, (project_id, invitee_id))
        if existing is None:
            existing = ProjectMembership(
                project_id=project_id,
                human_user_id=invitee_id,
                role="member",
                status="invited",
                invited_by_user_id=user.id,
                invited_at=now,
                updated_at=now,
            )
            session.add(existing)
        else:
            existing.status = "invited"
            existing.role = "member"
            existing.invited_by_user_id = user.id
            existing.invited_at = now
            existing.joined_at = None
            existing.updated_at = now
        session.add(
            ProjectActivity(
                project_id=project_id,
                activity_type="member_invited",
                actor_human_user_id=user.id,
                target_human_user_id=invitee_id,
                created_at=now,
            )
        )
    project.updated_at = now
    add_human_action_audit(
        session,
        human_user_id=user.id,
        human_session_id=human_session_id,
        action="project.members_invited",
        target_type="project",
        target_id=str(project.id),
        outcome="success",
        request_id=request_id,
        audit_metadata={"human_user_ids": [str(item) for item in human_user_ids]},
    )
    session.commit()
    return _project_detail(session, project=project, viewer_membership=membership)


def decide_project_invitation(
    session: Session,
    *,
    user: HumanUser,
    project_id: UUID,
    accept: bool,
    human_session_id: UUID | None,
    request_id: str,
) -> ProjectDetail | None:
    project, membership = _load_project_context(
        session, project_id=project_id, user=user, lock=True
    )
    if membership.status != "invited":
        raise ProjectMembershipConflictError
    now = utc_now()
    membership.status = "active" if accept else "declined"
    membership.joined_at = now if accept else None
    membership.updated_at = now
    session.add(
        ProjectActivity(
            project_id=project_id,
            activity_type="member_joined" if accept else "member_declined",
            actor_human_user_id=user.id,
            target_human_user_id=user.id,
            created_at=now,
        )
    )
    project.updated_at = now
    add_human_action_audit(
        session,
        human_user_id=user.id,
        human_session_id=human_session_id,
        action="project.invitation_accepted" if accept else "project.invitation_declined",
        target_type="project",
        target_id=str(project.id),
        outcome="success",
        request_id=request_id,
    )
    session.commit()
    if not accept:
        return None
    return _project_detail(session, project=project, viewer_membership=membership)


def update_project_status(
    session: Session,
    *,
    user: HumanUser,
    project_id: UUID,
    status: str,
    human_session_id: UUID | None,
    request_id: str,
) -> ProjectDetail:
    project, membership = _load_project_context(
        session, project_id=project_id, user=user, lock=True
    )
    _require_owner(project, membership)
    if project.status == status:
        raise ProjectMembershipConflictError
    now = utc_now()
    project.status = status
    project.archived_at = now if status == "archived" else None
    project.updated_at = now
    session.add(
        ProjectActivity(
            project_id=project_id,
            activity_type="archived" if status == "archived" else "restored",
            actor_human_user_id=user.id,
            created_at=now,
        )
    )
    add_human_action_audit(
        session,
        human_user_id=user.id,
        human_session_id=human_session_id,
        action=f"project.{status}",
        target_type="project",
        target_id=str(project.id),
        outcome="success",
        request_id=request_id,
    )
    session.commit()
    return _project_detail(session, project=project, viewer_membership=membership)
