from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, desc, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from agentpost.config import Settings
from agentpost.control.api_keys import (
    digest_human_key,
    generate_human_key,
    human_key_prefix,
)
from agentpost.control.models import (
    AgentOwnership,
    HumanAccessKey,
    HumanAgentGrant,
    HumanUser,
)
from agentpost.control.schemas import (
    AgentAccessResponse,
    HumanCreate,
    HumanProfile,
    HumanRegistrationResponse,
    OrbitAgent,
    OrbitDashboard,
    OrbitMessage,
    OrbitMetrics,
    OrbitTask,
)
from agentpost.identity.models import Agent, utc_now
from agentpost.messaging.models import AuditLog, Delivery, Message


class HumanEmailAlreadyRegisteredError(Exception):
    pass


class HumanNotFoundError(Exception):
    pass


class AgentAccessTargetNotFoundError(Exception):
    pass


class AgentAccessNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class AccessEntry:
    agent: Agent
    role: str
    granted_at: datetime


def human_profile(user: HumanUser) -> HumanProfile:
    return HumanProfile(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        status=user.status,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_seen_at=user.last_seen_at,
    )


def provision_human(
    session: Session,
    settings: Settings,
    payload: HumanCreate,
    *,
    request_id: str,
) -> HumanRegistrationResponse:
    if session.scalar(select(HumanUser.id).where(HumanUser.email == payload.email)) is not None:
        raise HumanEmailAlreadyRegisteredError(payload.email)

    now = utc_now()
    raw_key = generate_human_key()
    user = HumanUser(
        email=payload.email,
        display_name=payload.display_name,
        status="active",
        created_at=now,
        updated_at=now,
    )
    session.add(user)
    try:
        session.flush()
        session.add_all(
            [
                HumanAccessKey(
                    human_user_id=user.id,
                    key_digest=digest_human_key(raw_key, settings.human_api_key_pepper),
                    key_prefix=human_key_prefix(raw_key),
                    created_at=now,
                ),
                AuditLog(
                    actor_agent_id=None,
                    action="control.human_created",
                    target_type="human_user",
                    target_id=str(user.id),
                    outcome="success",
                    request_id=request_id,
                    audit_metadata={},
                    created_at=now,
                ),
            ]
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HumanEmailAlreadyRegisteredError(payload.email) from exc

    return HumanRegistrationResponse(
        user=human_profile(user),
        access_key=raw_key,
        access_key_prefix=human_key_prefix(raw_key),
    )


def list_humans(session: Session, *, limit: int) -> list[HumanProfile]:
    users = session.scalars(select(HumanUser).order_by(HumanUser.email).limit(limit)).all()
    return [human_profile(user) for user in users]


def _load_human_and_agent(
    session: Session,
    *,
    human_user_id: UUID,
    agent_id: UUID,
) -> tuple[HumanUser, Agent]:
    user = session.get(HumanUser, human_user_id)
    agent = session.scalar(select(Agent).where(Agent.id == agent_id).with_for_update())
    if user is None:
        raise HumanNotFoundError(str(human_user_id))
    if agent is None:
        raise AgentAccessTargetNotFoundError(str(agent_id))
    return user, agent


def grant_agent_access(
    session: Session,
    *,
    human_user_id: UUID,
    agent_id: UUID,
    role: str,
    request_id: str,
) -> AgentAccessResponse:
    user, agent = _load_human_and_agent(
        session,
        human_user_id=human_user_id,
        agent_id=agent_id,
    )
    now = utc_now()

    if role == "owner":
        session.execute(delete(AgentOwnership).where(AgentOwnership.agent_id == agent.id))
        session.execute(
            delete(HumanAgentGrant).where(
                HumanAgentGrant.human_user_id == user.id,
                HumanAgentGrant.agent_id == agent.id,
            )
        )
        session.add(
            AgentOwnership(
                agent_id=agent.id,
                human_user_id=user.id,
                assigned_at=now,
            )
        )
        agent.owner_id = str(user.id)
        granted_at = now
    else:
        ownership = session.get(AgentOwnership, agent.id)
        if ownership is not None and ownership.human_user_id == user.id:
            session.delete(ownership)
            agent.owner_id = None
        grant = session.scalar(
            select(HumanAgentGrant).where(
                HumanAgentGrant.human_user_id == user.id,
                HumanAgentGrant.agent_id == agent.id,
            )
        )
        if grant is None:
            grant = HumanAgentGrant(
                human_user_id=user.id,
                agent_id=agent.id,
                role=role,
                created_at=now,
                updated_at=now,
            )
            session.add(grant)
        else:
            grant.role = role
            grant.updated_at = now
        granted_at = grant.created_at

    session.add(
        AuditLog(
            actor_agent_id=None,
            action="control.agent_access_granted",
            target_type="agent",
            target_id=str(agent.id),
            outcome="success",
            request_id=request_id,
            audit_metadata={
                "human_user_id": str(user.id),
                "role": role,
            },
            created_at=now,
        )
    )
    session.commit()
    return AgentAccessResponse(
        human_user_id=user.id,
        agent_id=agent.id,
        agent_address=agent.address,
        role=role,
        granted_at=granted_at,
    )


def revoke_agent_access(
    session: Session,
    *,
    human_user_id: UUID,
    agent_id: UUID,
    request_id: str,
) -> None:
    user, agent = _load_human_and_agent(
        session,
        human_user_id=human_user_id,
        agent_id=agent_id,
    )
    removed = False
    ownership = session.get(AgentOwnership, agent.id)
    if ownership is not None and ownership.human_user_id == user.id:
        session.delete(ownership)
        agent.owner_id = None
        removed = True
    grant = session.scalar(
        select(HumanAgentGrant).where(
            HumanAgentGrant.human_user_id == user.id,
            HumanAgentGrant.agent_id == agent.id,
        )
    )
    if grant is not None:
        session.delete(grant)
        removed = True
    if not removed:
        session.rollback()
        raise AgentAccessNotFoundError(str(agent_id))

    session.add(
        AuditLog(
            actor_agent_id=None,
            action="control.agent_access_revoked",
            target_type="agent",
            target_id=str(agent.id),
            outcome="success",
            request_id=request_id,
            audit_metadata={"human_user_id": str(user.id)},
            created_at=utc_now(),
        )
    )
    session.commit()


def list_agent_access(session: Session, user: HumanUser) -> list[AccessEntry]:
    owners = session.execute(
        select(Agent, AgentOwnership.assigned_at)
        .join(AgentOwnership, AgentOwnership.agent_id == Agent.id)
        .where(AgentOwnership.human_user_id == user.id)
        .order_by(Agent.address)
    ).all()
    grants = session.execute(
        select(Agent, HumanAgentGrant.role, HumanAgentGrant.created_at)
        .join(HumanAgentGrant, HumanAgentGrant.agent_id == Agent.id)
        .where(HumanAgentGrant.human_user_id == user.id)
        .order_by(Agent.address)
    ).all()
    entries = [
        AccessEntry(agent=agent, role="owner", granted_at=assigned_at)
        for agent, assigned_at in owners
    ]
    entries.extend(
        AccessEntry(agent=agent, role=role, granted_at=created_at)
        for agent, role, created_at in grants
    )
    return sorted(entries, key=lambda entry: entry.agent.address)


def _message_rows(
    session: Session,
    *,
    agent_ids: set[UUID],
    limit: int,
) -> list[tuple[Message, Delivery, Agent, Agent]]:
    if not agent_ids:
        return []
    sender = aliased(Agent)
    recipient = aliased(Agent)
    return list(
        session.execute(
            select(Message, Delivery, sender, recipient)
            .join(Delivery, Delivery.message_id == Message.id)
            .join(sender, sender.id == Message.sender_agent_id)
            .join(recipient, recipient.id == Delivery.recipient_agent_id)
            .where(
                or_(
                    Message.sender_agent_id.in_(agent_ids),
                    Delivery.recipient_agent_id.in_(agent_ids),
                )
            )
            .order_by(desc(Message.created_at), desc(Message.id))
            .limit(limit)
        ).all()
    )


def _task_rows(
    session: Session,
    *,
    agent_ids: set[UUID],
    limit: int | None,
) -> list[tuple[Message, Delivery, Agent, Agent]]:
    if not agent_ids:
        return []
    sender = aliased(Agent)
    recipient = aliased(Agent)
    statement = (
        select(Message, Delivery, sender, recipient)
        .join(Delivery, Delivery.message_id == Message.id)
        .join(sender, sender.id == Message.sender_agent_id)
        .join(recipient, recipient.id == Delivery.recipient_agent_id)
        .where(
            Message.message_type == "task",
            or_(
                Message.sender_agent_id.in_(agent_ids),
                Delivery.recipient_agent_id.in_(agent_ids),
            ),
        )
        .order_by(desc(Message.created_at), desc(Message.id))
    )
    if limit is not None:
        statement = statement.limit(limit)
    return list(session.execute(statement).all())


def _results_for_tasks(session: Session, task_ids: list[str]) -> dict[str, Message]:
    if not task_ids:
        return {}
    results = session.scalars(
        select(Message)
        .where(
            Message.message_type == "result",
            Message.reply_to_message_id.in_(task_ids),
        )
        .order_by(Message.created_at, Message.id)
    ).all()
    return {result.reply_to_message_id: result for result in results if result.reply_to_message_id}


def _content_allowed(role_map: dict[UUID, str], sender_id: UUID, recipient_id: UUID) -> bool:
    roles = {role_map.get(sender_id), role_map.get(recipient_id)} - {None}
    return any(role != "auditor" for role in roles)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _work_state_for(message: Message, results: dict[str, Message]) -> str | None:
    if message.message_type == "task":
        result = results.get(message.id)
        if result is None or result.result_payload is None:
            return "pending"
        return str(result.result_payload.get("status", "pending"))
    if message.message_type == "result" and message.result_payload is not None:
        return str(message.result_payload.get("status"))
    return None


def _orbit_message(
    row: tuple[Message, Delivery, Agent, Agent],
    *,
    role_map: dict[UUID, str],
    task_results: dict[str, Message],
) -> OrbitMessage:
    message, delivery, sender, recipient = row
    content_allowed = _content_allowed(
        role_map,
        message.sender_agent_id,
        delivery.recipient_agent_id,
    )
    return OrbitMessage(
        message_id=message.id,
        sender_address=sender.address,
        recipient_address=recipient.address,
        subject=message.subject,
        message_type=message.message_type,
        priority=message.priority,
        content_format=message.content_format,
        content_body=message.content_body if content_allowed else None,
        content_redacted=not content_allowed,
        thread_id=message.thread_id,
        reply_to=message.reply_to_message_id,
        communication_state=delivery.delivery_status,
        work_state=_work_state_for(message, task_results),
        created_at=message.created_at,
    )


def list_orbit_messages(
    session: Session,
    user: HumanUser,
    *,
    limit: int,
) -> list[OrbitMessage]:
    entries = list_agent_access(session, user)
    role_map = {entry.agent.id: entry.role for entry in entries}
    rows = _message_rows(session, agent_ids=set(role_map), limit=limit)
    task_ids = [row[0].id for row in rows if row[0].message_type == "task"]
    task_results = _results_for_tasks(session, task_ids)
    return [_orbit_message(row, role_map=role_map, task_results=task_results) for row in rows]


def list_orbit_tasks(
    session: Session,
    user: HumanUser,
    *,
    limit: int,
) -> list[OrbitTask]:
    entries = list_agent_access(session, user)
    role_map = {entry.agent.id: entry.role for entry in entries}
    rows = _task_rows(session, agent_ids=set(role_map), limit=limit)
    results = _results_for_tasks(session, [row[0].id for row in rows])
    tasks: list[OrbitTask] = []
    for task, delivery, sender, recipient in rows:
        result = results.get(task.id)
        result_payload = result.result_payload if result is not None else None
        state = str(result_payload.get("status")) if result_payload else "pending"
        content_allowed = _content_allowed(
            role_map,
            task.sender_agent_id,
            delivery.recipient_agent_id,
        )
        instruction = (task.task_payload or {}).get("instruction")
        summary = result_payload.get("summary") if result_payload else None
        tasks.append(
            OrbitTask(
                task_message_id=task.id,
                subject=task.subject,
                requester_address=sender.address,
                assignee_address=recipient.address,
                instruction=(
                    str(instruction) if instruction is not None and content_allowed else None
                ),
                priority=task.priority,
                communication_state=delivery.delivery_status,
                work_state=state,
                result_message_id=result.id if result is not None else None,
                result_summary=str(summary) if summary is not None and content_allowed else None,
                created_at=task.created_at,
                updated_at=result.created_at if result is not None else task.created_at,
            )
        )
    return tasks


def build_orbit_dashboard(session: Session, user: HumanUser) -> OrbitDashboard:
    entries = list_agent_access(session, user)
    agent_ids = {entry.agent.id for entry in entries}
    role_map = {entry.agent.id: entry.role for entry in entries}
    tasks = list_orbit_tasks(session, user, limit=50)
    recent_rows = _message_rows(session, agent_ids=agent_ids, limit=12)
    recent_task_ids = [row[0].id for row in recent_rows if row[0].message_type == "task"]
    recent_task_results = _results_for_tasks(session, recent_task_ids)
    recent_messages = [
        _orbit_message(
            row,
            role_map=role_map,
            task_results=recent_task_results,
        )
        for row in recent_rows
    ]

    unread_by_agent: dict[UUID, int] = {}
    if agent_ids:
        unread_by_agent = dict(
            session.execute(
                select(Delivery.recipient_agent_id, func.count(Delivery.id))
                .where(
                    Delivery.recipient_agent_id.in_(agent_ids),
                    Delivery.delivery_status == "delivered",
                )
                .group_by(Delivery.recipient_agent_id)
            ).all()
        )

    pending_by_agent: dict[UUID, int] = {agent_id: 0 for agent_id in agent_ids}
    task_rows = _task_rows(session, agent_ids=agent_ids, limit=None)
    task_results = _results_for_tasks(session, [row[0].id for row in task_rows])
    for task, delivery, _, _ in task_rows:
        if task.id not in task_results and delivery.recipient_agent_id in pending_by_agent:
            pending_by_agent[delivery.recipient_agent_id] += 1

    pending_task_count = sum(task.id not in task_results for task, _, _, _ in task_rows)
    failed_task_count = sum(
        (result.result_payload or {}).get("status") == "failed" for result in task_results.values()
    )

    now = datetime.now(UTC)
    agents = [
        OrbitAgent(
            id=entry.agent.id,
            address=entry.agent.address,
            display_name=entry.agent.display_name,
            description=entry.agent.description,
            status=entry.agent.status,
            role=entry.role,
            capabilities=list(entry.agent.capabilities),
            last_seen_at=entry.agent.last_seen_at,
            unread_count=unread_by_agent.get(entry.agent.id, 0),
            pending_task_count=pending_by_agent.get(entry.agent.id, 0),
        )
        for entry in entries
    ]
    online_recently = sum(
        1
        for entry in entries
        if (seen := _as_utc(entry.agent.last_seen_at)) is not None
        and now - seen <= timedelta(minutes=5)
    )
    return OrbitDashboard(
        user=human_profile(user),
        metrics=OrbitMetrics(
            agent_count=len(entries),
            online_recently_count=online_recently,
            unread_delivery_count=sum(unread_by_agent.values()),
            pending_task_count=pending_task_count,
            failed_task_count=failed_task_count,
        ),
        agents=agents,
        recent_messages=recent_messages,
        tasks=tasks[:12],
    )
