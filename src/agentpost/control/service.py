from __future__ import annotations

import json
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
    HumanActionAudit,
    HumanAgentGrant,
    HumanUser,
    Organization,
)
from agentpost.control.organization_service import (
    list_orbit_organizations,
    list_organization_agent_access,
)
from agentpost.control.schemas import (
    AgentAccessResponse,
    HumanCreate,
    HumanProfile,
    HumanRegistrationResponse,
    OrbitAgent,
    OrbitDashboard,
    OrbitMessage,
    OrbitMessageAgent,
    OrbitMessageAttachment,
    OrbitMetrics,
    OrbitOrganizationReference,
    OrbitTask,
    OrbitThreadDetail,
    OrbitThreadSummary,
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


class AgentOwnerActionDeniedError(Exception):
    pass


class OrbitThreadNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class AccessEntry:
    agent: Agent
    role: str
    granted_at: datetime
    source: str = "direct"
    organization: Organization | None = None
    organization_role: str | None = None


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
        email_verified_at=now,
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
                    label="admin bootstrap",
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
    direct_entries = [
        AccessEntry(agent=agent, role="owner", granted_at=assigned_at)
        for agent, assigned_at in owners
    ]
    direct_entries.extend(
        AccessEntry(agent=agent, role=role, granted_at=created_at)
        for agent, role, created_at in grants
    )
    priority = {"owner": 4, "operator": 3, "viewer": 2, "auditor": 1}
    entries: dict[UUID, AccessEntry] = {}
    for entry in direct_entries:
        existing = entries.get(entry.agent.id)
        if existing is None or priority[entry.role] > priority[existing.role]:
            entries[entry.agent.id] = entry

    organization_role_projection = {
        "owner": "operator",
        "admin": "operator",
        "member": "viewer",
        "auditor": "auditor",
    }
    for organization_access in list_organization_agent_access(session, user):
        organization_entry = AccessEntry(
            agent=organization_access.agent,
            role=organization_role_projection[organization_access.membership_role],
            granted_at=organization_access.granted_at,
            source="organization",
            organization=organization_access.organization,
            organization_role=organization_access.membership_role,
        )
        existing = entries.get(organization_entry.agent.id)
        if existing is None or priority[organization_entry.role] > priority[existing.role]:
            entries[organization_entry.agent.id] = organization_entry
        elif existing.organization is None:
            entries[organization_entry.agent.id] = AccessEntry(
                agent=existing.agent,
                role=existing.role,
                granted_at=existing.granted_at,
                source=existing.source,
                organization=organization_access.organization,
                organization_role=organization_access.membership_role,
            )
    return sorted(entries.values(), key=lambda entry: entry.agent.address)


def disable_owned_agent(
    session: Session,
    *,
    user: HumanUser,
    agent_id: UUID,
    human_session_id: UUID | None,
    request_id: str,
) -> None:
    """Soft-delete one owned Agent while retaining its durable identity and history."""

    from agentpost.identity.models import AgentApiKey
    from agentpost.oauth.service import revoke_connector_oauth_tokens
    from agentpost.onboarding.models import AgentConnectorBinding, ConnectorInstance

    agent = session.scalar(
        select(Agent)
        .join(AgentOwnership, AgentOwnership.agent_id == Agent.id)
        .where(
            Agent.id == agent_id,
            AgentOwnership.human_user_id == user.id,
        )
        .with_for_update()
    )
    if agent is None:
        raise AgentOwnerActionDeniedError
    if agent.status == "disabled":
        return

    now = utc_now()
    binding = session.scalar(
        select(AgentConnectorBinding)
        .where(AgentConnectorBinding.agent_id == agent.id)
        .with_for_update()
    )
    connector = (
        session.get(ConnectorInstance, binding.connector_instance_id)
        if binding is not None
        else None
    )
    if binding is not None:
        session.delete(binding)
    if connector is not None:
        connector.status = "revoked"
        connector.revoked_at = connector.revoked_at or now
        connector.revocation_reason = "agent_deleted_by_owner"
        for credential in session.scalars(
            select(AgentApiKey).where(AgentApiKey.connector_instance_id == connector.id)
        ).all():
            credential.revoked_at = credential.revoked_at or now
        revoke_connector_oauth_tokens(session, connector.id, reason="agent_deleted")

    agent.status = "disabled"
    agent.updated_at = now
    session.add(
        HumanActionAudit(
            human_user_id=user.id,
            human_session_id=human_session_id,
            action="control.agent_deleted",
            target_type="agent",
            target_id=str(agent.id),
            outcome="success",
            request_id=request_id,
            audit_metadata={
                "address": agent.address,
                "handle": agent.handle,
                "connector_id": connector.connector_id if connector is not None else None,
                "deletion_mode": "soft_delete_preserve_history",
            },
            created_at=now,
        )
    )
    session.commit()


def _message_rows(
    session: Session,
    *,
    agent_ids: set[UUID],
    limit: int | None,
    thread_id: UUID | None = None,
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
            or_(
                Message.sender_agent_id.in_(agent_ids),
                Delivery.recipient_agent_id.in_(agent_ids),
            )
        )
        .order_by(desc(Message.created_at), desc(Message.id))
    )
    if thread_id is not None:
        statement = statement.where(Message.thread_id == thread_id)
    if limit is not None:
        statement = statement.limit(limit)
    return list(session.execute(statement).all())


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


def _connector_types_for_agents(session: Session, agent_ids: set[UUID]) -> dict[UUID, str]:
    if not agent_ids:
        return {}
    from agentpost.onboarding.models import AgentConnectorBinding, ConnectorInstance

    return dict(
        session.execute(
            select(AgentConnectorBinding.agent_id, ConnectorInstance.connector_type)
            .join(
                ConnectorInstance,
                ConnectorInstance.id == AgentConnectorBinding.connector_instance_id,
            )
            .where(
                AgentConnectorBinding.agent_id.in_(agent_ids),
                ConnectorInstance.status == "active",
            )
        ).all()
    )


def _orbit_message_agent(agent: Agent, connector_types: dict[UUID, str]) -> OrbitMessageAgent:
    return OrbitMessageAgent(
        id=agent.id,
        address=agent.address,
        handle=agent.handle,
        display_name=agent.display_name,
        agent_type=connector_types.get(agent.id),
    )


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
    connector_types: dict[UUID, str],
) -> OrbitMessage:
    message, delivery, sender, recipient = row
    content_allowed = _content_allowed(
        role_map,
        message.sender_agent_id,
        delivery.recipient_agent_id,
    )
    task_payload = message.task_payload or {}
    result_payload = message.result_payload or {}
    return OrbitMessage(
        message_id=message.id,
        sender=_orbit_message_agent(sender, connector_types),
        recipient=_orbit_message_agent(recipient, connector_types),
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
        requires_ack=message.requires_ack,
        task_instruction=(
            str(task_payload["instruction"])
            if content_allowed and task_payload.get("instruction") is not None
            else None
        ),
        task_expected_output=(
            str(task_payload["expected_output"])
            if content_allowed and task_payload.get("expected_output") is not None
            else None
        ),
        task_deadline=task_payload.get("deadline") if content_allowed else None,
        result_summary=(
            str(result_payload["summary"])
            if content_allowed and result_payload.get("summary") is not None
            else None
        ),
        attachments=(
            [
                OrbitMessageAttachment(
                    id=attachment.id,
                    filename=attachment.filename,
                    content_type=attachment.content_type,
                    size=attachment.size,
                )
                for attachment in message.attachments
            ]
            if content_allowed
            else []
        ),
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
    connector_types = _connector_types_for_agents(session, set(role_map))
    return [
        _orbit_message(
            row,
            role_map=role_map,
            task_results=task_results,
            connector_types=connector_types,
        )
        for row in rows
    ]


def _thread_organizations(
    entries_by_agent: dict[UUID, AccessEntry],
    participant_ids: set[UUID],
) -> list[OrbitOrganizationReference]:
    organizations: dict[UUID, OrbitOrganizationReference] = {}
    for agent_id in participant_ids:
        entry = entries_by_agent.get(agent_id)
        if entry is None or entry.organization is None:
            continue
        organizations[entry.organization.id] = OrbitOrganizationReference(
            id=entry.organization.id,
            slug=entry.organization.slug,
            name=entry.organization.name,
            membership_role=entry.organization_role,
        )
    return sorted(organizations.values(), key=lambda item: (item.name.casefold(), str(item.id)))


def _thread_rows_match_query(
    rows: list[tuple[Message, Delivery, Agent, Agent]],
    *,
    role_map: dict[UUID, str],
    organizations: list[OrbitOrganizationReference],
    query: str | None,
) -> bool:
    if query is None or not query.strip():
        return True
    needle = query.strip().casefold()
    searchable: list[str] = [item.name for item in organizations]
    for message, delivery, sender, recipient in rows:
        searchable.extend(
            [
                message.subject,
                sender.address,
                sender.handle or "",
                sender.display_name,
                recipient.address,
                recipient.handle or "",
                recipient.display_name,
            ]
        )
        if _content_allowed(role_map, message.sender_agent_id, delivery.recipient_agent_id):
            searchable.append(json.dumps(message.content_body, ensure_ascii=False, default=str))
            searchable.extend(attachment.filename for attachment in message.attachments)
    return any(needle in value.casefold() for value in searchable)


def _orbit_thread_data(
    session: Session,
    user: HumanUser,
    *,
    thread_id: UUID | None = None,
) -> tuple[
    list[AccessEntry],
    dict[UUID, str],
    dict[UUID, str],
    dict[UUID, list[tuple[Message, Delivery, Agent, Agent]]],
    dict[str, Message],
]:
    entries = list_agent_access(session, user)
    role_map = {entry.agent.id: entry.role for entry in entries}
    agent_ids = set(role_map)
    rows = _message_rows(session, agent_ids=agent_ids, limit=None, thread_id=thread_id)
    grouped: dict[UUID, list[tuple[Message, Delivery, Agent, Agent]]] = {}
    for row in rows:
        grouped.setdefault(row[0].thread_id, []).append(row)
    for values in grouped.values():
        values.sort(key=lambda row: (_as_utc(row[0].created_at), row[0].id))
    task_results = _results_for_tasks(
        session,
        [row[0].id for row in rows if row[0].message_type == "task"],
    )
    return (
        entries,
        role_map,
        _connector_types_for_agents(session, agent_ids),
        grouped,
        task_results,
    )


def list_orbit_threads(
    session: Session,
    user: HumanUser,
    *,
    limit: int,
    query: str | None,
    agent_id: UUID | None = None,
) -> list[OrbitThreadSummary]:
    entries, role_map, connector_types, grouped, task_results = _orbit_thread_data(
        session,
        user,
    )
    entries_by_agent = {entry.agent.id: entry for entry in entries}
    if agent_id is not None and agent_id not in entries_by_agent:
        return []
    summaries: list[OrbitThreadSummary] = []
    for thread_id, rows in grouped.items():
        participant_agents: dict[UUID, Agent] = {}
        for _, _, sender, recipient in rows:
            participant_agents[sender.id] = sender
            participant_agents[recipient.id] = recipient
        participant_ids = set(participant_agents)
        if agent_id is not None and agent_id not in participant_ids:
            continue
        organizations = _thread_organizations(entries_by_agent, participant_ids)
        if not _thread_rows_match_query(
            rows,
            role_map=role_map,
            organizations=organizations,
            query=query,
        ):
            continue
        first_message = rows[0][0]
        latest_message, latest_delivery, _, _ = rows[-1]
        latest_allowed = _content_allowed(
            role_map,
            latest_message.sender_agent_id,
            latest_delivery.recipient_agent_id,
        )
        pending_tasks = sum(
            message.message_type == "task" and message.id not in task_results
            for message, _, _, _ in rows
        )
        exceptions = sum(
            delivery.delivery_status in {"failed", "expired", "rejected"}
            or message.message_type == "error"
            or _work_state_for(message, task_results) == "failed"
            for message, delivery, _, _ in rows
        )
        summaries.append(
            OrbitThreadSummary(
                thread_id=thread_id,
                topic=first_message.subject or latest_message.subject or "无主题对话",
                participants=[
                    _orbit_message_agent(agent, connector_types)
                    for agent in sorted(
                        participant_agents.values(),
                        key=lambda item: (item.display_name.casefold(), item.address),
                    )
                ],
                organizations=organizations,
                latest_message_id=latest_message.id,
                latest_message_type=latest_message.message_type,
                latest_message_summary=(latest_message.content_body if latest_allowed else None),
                latest_content_redacted=not latest_allowed,
                latest_activity_at=latest_message.created_at,
                message_count=len(rows),
                attachment_count=sum(len(message.attachments) for message, _, _, _ in rows),
                pending_task_count=pending_tasks,
                exception_count=exceptions,
                agent_pending_read_count=sum(
                    delivery.delivery_status == "delivered" and delivery.read_at is None
                    for _, delivery, _, _ in rows
                ),
            )
        )
    summaries.sort(
        key=lambda item: (_as_utc(item.latest_activity_at), item.latest_message_id),
        reverse=True,
    )
    return summaries[:limit]


def get_orbit_thread(
    session: Session,
    user: HumanUser,
    *,
    thread_id: UUID,
) -> OrbitThreadDetail:
    entries, role_map, connector_types, grouped, task_results = _orbit_thread_data(
        session,
        user,
        thread_id=thread_id,
    )
    rows = grouped.get(thread_id)
    if not rows:
        raise OrbitThreadNotFoundError(str(thread_id))
    participant_agents: dict[UUID, Agent] = {}
    for _, _, sender, recipient in rows:
        participant_agents[sender.id] = sender
        participant_agents[recipient.id] = recipient
    entries_by_agent = {entry.agent.id: entry for entry in entries}
    return OrbitThreadDetail(
        thread_id=thread_id,
        topic=rows[0][0].subject or rows[-1][0].subject or "无主题对话",
        participants=[
            _orbit_message_agent(agent, connector_types)
            for agent in sorted(
                participant_agents.values(),
                key=lambda item: (item.display_name.casefold(), item.address),
            )
        ],
        organizations=_thread_organizations(entries_by_agent, set(participant_agents)),
        messages=[
            _orbit_message(
                row,
                role_map=role_map,
                task_results=task_results,
                connector_types=connector_types,
            )
            for row in rows
        ],
    )


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


def _current_connectors_by_agent(session: Session, agent_ids: set[UUID]) -> dict[UUID, object]:
    if not agent_ids:
        return {}
    from agentpost.onboarding.models import AgentConnectorBinding, ConnectorInstance

    return {
        agent_id: connector
        for agent_id, connector in session.execute(
            select(AgentConnectorBinding.agent_id, ConnectorInstance)
            .join(
                ConnectorInstance,
                ConnectorInstance.id == AgentConnectorBinding.connector_instance_id,
            )
            .where(AgentConnectorBinding.agent_id.in_(agent_ids))
        ).all()
    }


def _agent_connection_state(connector: object | None, now: datetime) -> str:
    if connector is None:
        return "disconnected"
    if getattr(connector, "status", None) != "active":
        return "connection_error"
    if getattr(connector, "health_status", None) == "error" or getattr(
        connector,
        "last_error_code",
        None,
    ):
        return "connection_error"
    heartbeat = _as_utc(getattr(connector, "last_heartbeat_at", None))
    if heartbeat is None:
        return "awaiting_agent"
    if now - heartbeat > timedelta(minutes=5):
        return "offline"
    return "connected"


def build_orbit_dashboard(session: Session, user: HumanUser) -> OrbitDashboard:
    from agentpost.control.approval_service import (
        list_human_approval_requests,
        pending_human_approval_count,
    )

    entries = [
        entry for entry in list_agent_access(session, user) if entry.agent.status != "disabled"
    ]
    agent_ids = {entry.agent.id for entry in entries}
    role_map = {entry.agent.id: entry.role for entry in entries}
    tasks = list_orbit_tasks(session, user, limit=50)
    recent_rows = _message_rows(session, agent_ids=agent_ids, limit=12)
    recent_task_ids = [row[0].id for row in recent_rows if row[0].message_type == "task"]
    recent_task_results = _results_for_tasks(session, recent_task_ids)
    connector_types = _connector_types_for_agents(session, agent_ids)
    recent_messages = [
        _orbit_message(
            row,
            role_map=role_map,
            task_results=recent_task_results,
            connector_types=connector_types,
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
    current_connectors = _current_connectors_by_agent(session, agent_ids)
    agents: list[OrbitAgent] = []
    for entry in entries:
        connector = current_connectors.get(entry.agent.id)
        agents.append(
            OrbitAgent(
                id=entry.agent.id,
                address=entry.agent.address,
                handle=entry.agent.handle,
                display_name=entry.agent.display_name,
                description=entry.agent.description,
                status=entry.agent.status,
                role=entry.role,
                access_source=entry.source,
                organization=(
                    OrbitOrganizationReference(
                        id=entry.organization.id,
                        slug=entry.organization.slug,
                        name=entry.organization.name,
                        membership_role=entry.organization_role,
                    )
                    if entry.organization is not None
                    else None
                ),
                capabilities=list(entry.agent.capabilities),
                last_seen_at=entry.agent.last_seen_at,
                connection_state=_agent_connection_state(connector, now),
                current_connector_type=getattr(connector, "connector_type", None),
                current_connector_name=getattr(connector, "display_name", None),
                current_connector_device=getattr(connector, "device_name", None),
                current_connector_version=getattr(connector, "client_version", None),
                current_connector_health=getattr(connector, "health_status", None),
                current_connector_last_heartbeat_at=getattr(
                    connector,
                    "last_heartbeat_at",
                    None,
                ),
                current_connector_error_code=getattr(connector, "last_error_code", None),
                unread_count=unread_by_agent.get(entry.agent.id, 0),
                pending_task_count=pending_by_agent.get(entry.agent.id, 0),
            )
        )
    online_recently = sum(
        1
        for entry in entries
        if (seen := _as_utc(entry.agent.last_seen_at)) is not None
        and now - seen <= timedelta(minutes=5)
    )
    connected_agent_count = sum(agent.connection_state == "connected" for agent in agents)
    return OrbitDashboard(
        user=human_profile(user),
        metrics=OrbitMetrics(
            agent_count=len(entries),
            connected_agent_count=connected_agent_count,
            online_recently_count=online_recently,
            unread_delivery_count=sum(unread_by_agent.values()),
            pending_task_count=pending_task_count,
            failed_task_count=failed_task_count,
            pending_approval_count=pending_human_approval_count(session, user=user),
        ),
        organizations=list_orbit_organizations(session, user),
        agents=agents,
        recent_messages=recent_messages,
        tasks=tasks[:12],
        approvals=list_human_approval_requests(
            session,
            user=user,
            limit=12,
            approval_status=None,
        ),
    )
