from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, desc, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from agentpost.accounts.usernames import (
    HumanUsernameAlreadyRegisteredError,
    available_human_username,
)
from agentpost.attachments.models import Attachment
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
    HumanThreadArchive,
    HumanThreadView,
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
    HumanUsernameUpdate,
    OrbitAgent,
    OrbitDashboard,
    OrbitMessage,
    OrbitMessageAgent,
    OrbitMessageAttachment,
    OrbitMetrics,
    OrbitOrganizationReference,
    OrbitTask,
    OrbitThreadArchiveState,
    OrbitThreadDetail,
    OrbitThreadSummary,
    OrbitThreadViewState,
)
from agentpost.identity.models import Agent, utc_now
from agentpost.messaging.models import AuditLog, Delivery, Message
from agentpost.onboarding.connectivity import connector_connection_state


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


class OrbitAttachmentNotFoundError(Exception):
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
        username=user.username,
        display_name=user.display_name,
        status=user.status,
        default_agent_id=user.default_agent_id,
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
    username = available_human_username(
        session,
        requested=payload.username,
        email=payload.email,
    )
    user = HumanUser(
        email=payload.email,
        username=username,
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
        if session.scalar(select(HumanUser.id).where(HumanUser.username == username)) is not None:
            raise HumanUsernameAlreadyRegisteredError(username) from exc
        raise HumanEmailAlreadyRegisteredError(payload.email) from exc

    return HumanRegistrationResponse(
        user=human_profile(user),
        access_key=raw_key,
        access_key_prefix=human_key_prefix(raw_key),
    )


def list_humans(session: Session, *, limit: int) -> list[HumanProfile]:
    users = session.scalars(select(HumanUser).order_by(HumanUser.email).limit(limit)).all()
    return [human_profile(user) for user in users]


def update_human_username(
    session: Session,
    *,
    user: HumanUser,
    payload: HumanUsernameUpdate,
    human_session_id: UUID | None,
    request_id: str,
) -> HumanProfile:
    """Update the current Human's public unique username without changing identity links."""

    if payload.username == user.username:
        return human_profile(user)
    if (
        session.scalar(
            select(HumanUser.id).where(
                HumanUser.username == payload.username,
                HumanUser.id != user.id,
            )
        )
        is not None
    ):
        raise HumanUsernameAlreadyRegisteredError(payload.username)

    previous_username = user.username
    user.username = payload.username
    user.updated_at = utc_now()
    session.add(
        HumanActionAudit(
            human_user_id=user.id,
            human_session_id=human_session_id,
            action="control.human_username_updated",
            target_type="human_user",
            target_id=str(user.id),
            outcome="success",
            request_id=request_id,
            audit_metadata={
                "previous_username": previous_username,
                "username": payload.username,
            },
            created_at=utc_now(),
        )
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HumanUsernameAlreadyRegisteredError(payload.username) from exc
    session.refresh(user)
    return human_profile(user)


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

    previous_owner_id: UUID | None = None
    existing_ownership = session.get(AgentOwnership, agent.id)
    if existing_ownership is not None:
        previous_owner_id = existing_ownership.human_user_id

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
        session.flush()
        ensure_human_default_agent(session, user=user)
        if previous_owner_id is not None and previous_owner_id != user.id:
            previous_owner = session.get(HumanUser, previous_owner_id)
            if previous_owner is not None:
                ensure_human_default_agent(session, user=previous_owner)
        granted_at = now
    else:
        ownership = session.get(AgentOwnership, agent.id)
        if ownership is not None and ownership.human_user_id == user.id:
            session.delete(ownership)
            agent.owner_id = None
            session.flush()
            ensure_human_default_agent(session, user=user)
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
        session.flush()
        ensure_human_default_agent(session, user=user)
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


def ensure_human_default_agent(session: Session, *, user: HumanUser) -> UUID | None:
    """Keep a Human's default Agent pointed at an active Agent they own."""

    if user.default_agent_id is not None:
        current = session.scalar(
            select(Agent.id)
            .join(AgentOwnership, AgentOwnership.agent_id == Agent.id)
            .where(
                Agent.id == user.default_agent_id,
                AgentOwnership.human_user_id == user.id,
                Agent.status == "active",
            )
        )
        if current is not None:
            return current

    replacement = session.scalar(
        select(Agent.id)
        .join(AgentOwnership, AgentOwnership.agent_id == Agent.id)
        .where(
            AgentOwnership.human_user_id == user.id,
            Agent.status == "active",
        )
        .order_by(AgentOwnership.assigned_at, Agent.address, Agent.id)
        .limit(1)
    )
    user.default_agent_id = replacement
    return replacement


def set_human_default_agent(
    session: Session,
    *,
    user: HumanUser,
    agent_id: UUID,
    human_session_id: UUID | None,
    request_id: str,
) -> None:
    """Select the active owned Agent used for Human-name first contact."""

    agent = session.scalar(
        select(Agent)
        .join(AgentOwnership, AgentOwnership.agent_id == Agent.id)
        .where(
            Agent.id == agent_id,
            AgentOwnership.human_user_id == user.id,
            Agent.status == "active",
        )
        .with_for_update()
    )
    if agent is None:
        raise AgentOwnerActionDeniedError
    previous_agent_id = user.default_agent_id
    user.default_agent_id = agent.id
    session.add(
        HumanActionAudit(
            human_user_id=user.id,
            human_session_id=human_session_id,
            action="control.default_agent_updated",
            target_type="agent",
            target_id=str(agent.id),
            outcome="success",
            request_id=request_id,
            audit_metadata={
                "previous_agent_id": str(previous_agent_id) if previous_agent_id else None,
                "default_agent_id": str(agent.id),
            },
            created_at=utc_now(),
        )
    )
    session.commit()


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
    session.flush()
    ensure_human_default_agent(session, user=user)
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
    rows = list(session.execute(statement).all())
    rows = _deduplicate_channel_rows(rows)
    return rows[:limit] if limit is not None else rows


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
    rows = list(session.execute(statement).all())
    rows = _deduplicate_channel_rows(rows)
    return rows[:limit] if limit is not None else rows


def _deduplicate_channel_rows(
    rows: list[tuple[Message, Delivery, Agent, Agent]],
) -> list[tuple[Message, Delivery, Agent, Agent]]:
    result: list[tuple[Message, Delivery, Agent, Agent]] = []
    seen_events: set[str] = set()
    for row in rows:
        event_id = (row[0].message_metadata or {}).get("organization_event_id")
        if event_id:
            if str(event_id) in seen_events:
                continue
            seen_events.add(str(event_id))
        result.append(row)
    return result


def _responses_for_tasks(session: Session, task_ids: list[str]) -> dict[str, Message]:
    if not task_ids:
        return {}
    task_senders = dict(
        session.execute(
            select(Message.id, Message.sender_agent_id).where(Message.id.in_(task_ids))
        ).all()
    )
    replies = session.scalars(
        select(Message)
        .where(
            Message.reply_to_message_id.in_(task_ids),
        )
        .order_by(Message.created_at, Message.id)
    ).all()
    responses: dict[str, Message] = {}
    for reply in replies:
        task_id = reply.reply_to_message_id
        if task_id is None:
            continue
        if reply.sender_agent_id == task_senders.get(task_id):
            continue
        current = responses.get(task_id)
        # A structured result remains authoritative. Otherwise, a direct reply
        # is sufficient evidence that this round of the task was handled.
        if current is None or reply.message_type == "result" or current.message_type != "result":
            responses[task_id] = reply
    return responses


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


def _owner_humans_for_agents(
    session: Session,
    agent_ids: set[UUID],
) -> dict[UUID, HumanUser]:
    if not agent_ids:
        return {}
    return {
        agent_id: owner
        for agent_id, owner in session.execute(
            select(AgentOwnership.agent_id, HumanUser)
            .join(HumanUser, HumanUser.id == AgentOwnership.human_user_id)
            .where(AgentOwnership.agent_id.in_(agent_ids))
        ).all()
    }


def _orbit_message_agent(
    agent: Agent,
    connector_types: dict[UUID, str],
    owner_humans: dict[UUID, HumanUser],
    current_human_id: UUID,
) -> OrbitMessageAgent:
    owner = owner_humans.get(agent.id)
    return OrbitMessageAgent(
        id=agent.id,
        address=agent.address,
        handle=agent.handle,
        display_name=agent.display_name,
        agent_type=connector_types.get(agent.id),
        owner_display_name=owner.display_name if owner is not None else None,
        owner_username=owner.username if owner is not None else None,
        owned_by_current_human=owner is not None and owner.id == current_human_id,
    )


def _requested_responder_agents(
    metadata: dict[str, object],
    agents_by_id: dict[UUID, Agent],
    connector_types: dict[UUID, str],
    owner_humans: dict[UUID, HumanUser],
    current_human_id: UUID,
) -> list[OrbitMessageAgent]:
    responders: list[OrbitMessageAgent] = []
    for raw_agent_id in metadata.get("requested_responder_agent_ids", []):
        try:
            agent_id = UUID(str(raw_agent_id))
        except (TypeError, ValueError):
            continue
        agent = agents_by_id.get(agent_id)
        if agent is None:
            continue
        responders.append(
            _orbit_message_agent(
                agent,
                connector_types,
                owner_humans,
                current_human_id,
            )
        )
    return responders


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _work_state_for(message: Message, responses: dict[str, Message]) -> str | None:
    if message.message_type == "task":
        response = responses.get(message.id)
        if response is None:
            return "pending"
        if response.message_type == "result" and response.result_payload is not None:
            return str(response.result_payload.get("status", "completed"))
        return "completed"
    if message.message_type == "result" and message.result_payload is not None:
        return str(message.result_payload.get("status"))
    return None


def _orbit_message(
    row: tuple[Message, Delivery, Agent, Agent],
    *,
    role_map: dict[UUID, str],
    task_results: dict[str, Message],
    connector_types: dict[UUID, str],
    owner_humans: dict[UUID, HumanUser],
    agents_by_id: dict[UUID, Agent],
    current_human_id: UUID,
) -> OrbitMessage:
    message, delivery, sender, recipient = row
    content_allowed = _content_allowed(
        role_map,
        message.sender_agent_id,
        delivery.recipient_agent_id,
    )
    task_payload = message.task_payload or {}
    result_payload = message.result_payload or {}
    metadata = message.message_metadata or {}
    return OrbitMessage(
        message_id=message.id,
        sender=_orbit_message_agent(
            sender,
            connector_types,
            owner_humans,
            current_human_id,
        ),
        recipient=_orbit_message_agent(
            recipient,
            connector_types,
            owner_humans,
            current_human_id,
        ),
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
        channel_scope=(
            "organization" if metadata.get("channel_scope") == "organization" else "direct"
        ),
        organization_id=(
            UUID(str(metadata["organization_id"]))
            if metadata.get("channel_scope") == "organization" and metadata.get("organization_id")
            else None
        ),
        organization_name=(
            str(metadata["organization_name"]) if metadata.get("organization_name") else None
        ),
        requested_responder_addresses=[
            str(address) for address in metadata.get("requested_responder_addresses", [])
        ],
        requested_responders=_requested_responder_agents(
            metadata,
            agents_by_id,
            connector_types,
            owner_humans,
            current_human_id,
        ),
        organization_recipient_count=int(metadata.get("organization_recipient_count") or 0),
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
    entries_by_agent = {entry.agent.id: entry for entry in entries}
    agents_by_id = {entry.agent.id: entry.agent for entry in entries}
    rows = [
        row
        for row in _message_rows(session, agent_ids=set(role_map), limit=limit)
        if _row_visible_after_access_grant(row, entries_by_agent)
    ]
    task_ids = [row[0].id for row in rows if row[0].message_type == "task"]
    task_results = _responses_for_tasks(session, task_ids)
    connector_types = _connector_types_for_agents(session, set(role_map))
    owner_humans = _owner_humans_for_agents(
        session,
        set(role_map) | {agent.id for row in rows for agent in row[2:]},
    )
    return [
        _orbit_message(
            row,
            role_map=role_map,
            task_results=task_results,
            connector_types=connector_types,
            owner_humans=owner_humans,
            agents_by_id=agents_by_id,
            current_human_id=user.id,
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


def _row_visible_after_access_grant(
    row: tuple[Message, Delivery, Agent, Agent],
    entries_by_agent: dict[UUID, AccessEntry],
) -> bool:
    """Do not expose pre-assignment history through organization-derived access."""

    return _message_visible_after_access_grant(
        row[0],
        recipient_agent_id=row[1].recipient_agent_id,
        entries_by_agent=entries_by_agent,
    )


def _message_visible_after_access_grant(
    message: Message,
    *,
    recipient_agent_id: UUID,
    entries_by_agent: dict[UUID, AccessEntry],
) -> bool:
    created_at = _as_utc(message.created_at)
    for participant_id in (message.sender_agent_id, recipient_agent_id):
        entry = entries_by_agent.get(participant_id)
        if entry is None:
            continue
        if entry.source != "organization":
            return True
        organization = entry.organization
        metadata = message.message_metadata or {}
        if (
            organization is not None
            and created_at >= _as_utc(entry.granted_at)
            and metadata.get("channel_scope") == "organization"
            and metadata.get("organization_id") == str(organization.id)
        ):
            return True
    return False


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
    dict[UUID, HumanUser],
    dict[UUID, list[tuple[Message, Delivery, Agent, Agent]]],
    dict[str, Message],
]:
    entries = list_agent_access(session, user)
    role_map = {entry.agent.id: entry.role for entry in entries}
    entries_by_agent = {entry.agent.id: entry for entry in entries}
    agent_ids = set(role_map)
    rows = [
        row
        for row in _message_rows(session, agent_ids=agent_ids, limit=None, thread_id=thread_id)
        if _row_visible_after_access_grant(row, entries_by_agent)
    ]
    grouped: dict[UUID, list[tuple[Message, Delivery, Agent, Agent]]] = {}
    for row in rows:
        grouped.setdefault(row[0].thread_id, []).append(row)
    for values in grouped.values():
        values.sort(key=lambda row: (_as_utc(row[0].created_at), row[0].id))
    task_results = _responses_for_tasks(
        session,
        [row[0].id for row in rows if row[0].message_type == "task"],
    )
    return (
        entries,
        role_map,
        _connector_types_for_agents(session, agent_ids),
        _owner_humans_for_agents(
            session,
            agent_ids | {agent.id for row in rows for agent in row[2:]},
        ),
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
    archived: bool = False,
) -> list[OrbitThreadSummary]:
    entries, role_map, connector_types, owner_humans, grouped, task_results = _orbit_thread_data(
        session,
        user,
    )
    entries_by_agent = {entry.agent.id: entry for entry in entries}
    if agent_id is not None and agent_id not in entries_by_agent:
        return []
    thread_views = {
        view.thread_id: view
        for view in session.scalars(
            select(HumanThreadView).where(HumanThreadView.human_user_id == user.id)
        ).all()
    }
    thread_archives = {
        archive.thread_id: archive
        for archive in session.scalars(
            select(HumanThreadArchive).where(HumanThreadArchive.human_user_id == user.id)
        ).all()
    }
    summaries: list[OrbitThreadSummary] = []
    for thread_id, rows in grouped.items():
        thread_archive = thread_archives.get(thread_id)
        if archived != (thread_archive is not None):
            continue
        participant_agents: dict[UUID, Agent] = {}
        for _, _, sender, recipient in rows:
            participant_agents[sender.id] = sender
            participant_agents[recipient.id] = recipient
        participant_ids = set(participant_agents)
        if agent_id is not None and agent_id not in participant_ids:
            continue
        organization_message = next(
            (
                message
                for message, _, _, _ in rows
                if (message.message_metadata or {}).get("channel_scope") == "organization"
            ),
            None,
        )
        is_organization_channel = organization_message is not None
        organization_metadata = (
            organization_message.message_metadata or {} if organization_message is not None else {}
        )
        organizations = (
            _thread_organizations(entries_by_agent, participant_ids)
            if is_organization_channel
            else []
        )
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
        latest_sender_projection = _orbit_message_agent(
            rows[-1][2], connector_types, owner_humans, user.id
        )
        latest_recipient_projection = _orbit_message_agent(
            rows[-1][3], connector_types, owner_humans, user.id
        )
        latest_work_state = _work_state_for(latest_message, task_results)
        if exceptions:
            conversation_state = "needs_attention"
        elif latest_work_state == "completed":
            conversation_state = "completed"
        elif pending_tasks:
            conversation_state = "in_progress"
        elif latest_recipient_projection.owned_by_current_human:
            conversation_state = "waiting_for_me"
        elif latest_sender_projection.owned_by_current_human:
            conversation_state = "waiting_for_other"
        else:
            conversation_state = "updated"
        thread_view = thread_views.get(thread_id)
        human_view_state = (
            "viewed"
            if thread_view is not None
            and thread_view.viewed_through_message_id == latest_message.id
            else "unread"
        )
        summaries.append(
            OrbitThreadSummary(
                thread_id=thread_id,
                topic=first_message.subject or latest_message.subject or "无主题对话",
                participants=[
                    _orbit_message_agent(
                        agent,
                        connector_types,
                        owner_humans,
                        user.id,
                    )
                    for agent in sorted(
                        participant_agents.values(),
                        key=lambda item: (item.display_name.casefold(), item.address),
                    )
                ],
                organizations=organizations,
                channel_scope=("organization" if is_organization_channel else "direct"),
                organization_id=(
                    UUID(str(organization_metadata["organization_id"]))
                    if organization_metadata.get("organization_id")
                    else None
                ),
                organization_name=(
                    str(organization_metadata["organization_name"])
                    if organization_metadata.get("organization_name")
                    else None
                ),
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
                latest_sender=latest_sender_projection,
                latest_recipient=latest_recipient_projection,
                conversation_state=conversation_state,
                human_view_state=human_view_state,
                human_viewed_at=thread_view.viewed_at if thread_view is not None else None,
                archived_at=thread_archive.archived_at if thread_archive is not None else None,
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
    entries, role_map, connector_types, owner_humans, grouped, task_results = _orbit_thread_data(
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
    agents_by_id = {entry.agent.id: entry.agent for entry in entries}
    thread_view = session.get(HumanThreadView, (user.id, thread_id))
    thread_archive = session.get(HumanThreadArchive, (user.id, thread_id))
    latest_message = rows[-1][0]
    return OrbitThreadDetail(
        thread_id=thread_id,
        topic=rows[0][0].subject or rows[-1][0].subject or "无主题对话",
        participants=[
            _orbit_message_agent(
                agent,
                connector_types,
                owner_humans,
                user.id,
            )
            for agent in sorted(
                participant_agents.values(),
                key=lambda item: (item.display_name.casefold(), item.address),
            )
        ],
        organizations=(
            _thread_organizations(entries_by_agent, set(participant_agents))
            if any(
                (message.message_metadata or {}).get("channel_scope") == "organization"
                for message, _, _, _ in rows
            )
            else []
        ),
        messages=[
            _orbit_message(
                row,
                role_map=role_map,
                task_results=task_results,
                connector_types=connector_types,
                owner_humans=owner_humans,
                agents_by_id=agents_by_id,
                current_human_id=user.id,
            )
            for row in rows
        ],
        human_view_state=(
            "viewed"
            if thread_view is not None
            and thread_view.viewed_through_message_id == latest_message.id
            else "unread"
        ),
        human_viewed_at=thread_view.viewed_at if thread_view is not None else None,
        archived_at=thread_archive.archived_at if thread_archive is not None else None,
    )


def mark_orbit_thread_viewed(
    session: Session,
    user: HumanUser,
    *,
    thread_id: UUID,
) -> OrbitThreadViewState:
    _, _, _, _, grouped, _ = _orbit_thread_data(session, user, thread_id=thread_id)
    rows = grouped.get(thread_id)
    if not rows:
        raise OrbitThreadNotFoundError(str(thread_id))
    latest_message = rows[-1][0]
    viewed_at = utc_now()
    thread_view = session.get(HumanThreadView, (user.id, thread_id))
    if thread_view is None:
        thread_view = HumanThreadView(
            human_user_id=user.id,
            thread_id=thread_id,
            viewed_through_message_id=latest_message.id,
            viewed_at=viewed_at,
        )
        session.add(thread_view)
    else:
        thread_view.viewed_through_message_id = latest_message.id
        thread_view.viewed_at = viewed_at
    session.commit()
    return OrbitThreadViewState(
        thread_id=thread_id,
        viewed_through_message_id=latest_message.id,
        viewed_at=viewed_at,
    )


def archive_orbit_thread(
    session: Session,
    user: HumanUser,
    *,
    thread_id: UUID,
) -> OrbitThreadArchiveState:
    _, _, _, _, grouped, _ = _orbit_thread_data(session, user, thread_id=thread_id)
    if not grouped.get(thread_id):
        raise OrbitThreadNotFoundError(str(thread_id))
    archived_at = utc_now()
    thread_archive = session.get(HumanThreadArchive, (user.id, thread_id))
    if thread_archive is None:
        thread_archive = HumanThreadArchive(
            human_user_id=user.id,
            thread_id=thread_id,
            archived_at=archived_at,
        )
        session.add(thread_archive)
    else:
        archived_at = thread_archive.archived_at
    session.commit()
    return OrbitThreadArchiveState(
        thread_id=thread_id,
        archived=True,
        archived_at=archived_at,
    )


def restore_orbit_thread(
    session: Session,
    user: HumanUser,
    *,
    thread_id: UUID,
) -> OrbitThreadArchiveState:
    _, _, _, _, grouped, _ = _orbit_thread_data(session, user, thread_id=thread_id)
    if not grouped.get(thread_id):
        raise OrbitThreadNotFoundError(str(thread_id))
    thread_archive = session.get(HumanThreadArchive, (user.id, thread_id))
    if thread_archive is not None:
        session.delete(thread_archive)
        session.commit()
    return OrbitThreadArchiveState(thread_id=thread_id, archived=False)


def get_orbit_attachment(
    session: Session,
    user: HumanUser,
    *,
    attachment_id: UUID,
) -> Attachment:
    attachment = session.get(Attachment, attachment_id)
    if attachment is None or attachment.state != "attached" or attachment.message_id is None:
        raise OrbitAttachmentNotFoundError(str(attachment_id))

    entries = list_agent_access(session, user)
    role_map = {entry.agent.id: entry.role for entry in entries}
    entries_by_agent = {entry.agent.id: entry for entry in entries}
    if not role_map:
        raise OrbitAttachmentNotFoundError(str(attachment_id))

    deliveries = session.execute(
        select(Message, Delivery.recipient_agent_id)
        .join(Delivery, Delivery.message_id == Message.id)
        .where(
            Message.id == attachment.message_id,
            or_(
                Message.sender_agent_id.in_(role_map),
                Delivery.recipient_agent_id.in_(role_map),
            ),
        )
    ).all()
    if not any(
        _content_allowed(role_map, message.sender_agent_id, recipient_id)
        and _message_visible_after_access_grant(
            message,
            recipient_agent_id=recipient_id,
            entries_by_agent=entries_by_agent,
        )
        for message, recipient_id in deliveries
    ):
        raise OrbitAttachmentNotFoundError(str(attachment_id))
    return attachment


def list_orbit_tasks(
    session: Session,
    user: HumanUser,
    *,
    limit: int,
) -> list[OrbitTask]:
    entries = list_agent_access(session, user)
    role_map = {entry.agent.id: entry.role for entry in entries}
    entries_by_agent = {entry.agent.id: entry for entry in entries}
    rows = [
        row
        for row in _task_rows(session, agent_ids=set(role_map), limit=limit)
        if _row_visible_after_access_grant(row, entries_by_agent)
    ]
    results = _responses_for_tasks(session, [row[0].id for row in rows])
    tasks: list[OrbitTask] = []
    for task, delivery, sender, recipient in rows:
        response = results.get(task.id)
        result_payload = (
            response.result_payload
            if response is not None and response.message_type == "result"
            else None
        )
        state = _work_state_for(task, results) or "pending"
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
                result_message_id=(
                    response.id
                    if response is not None and response.message_type == "result"
                    else None
                ),
                result_summary=str(summary) if summary is not None and content_allowed else None,
                created_at=task.created_at,
                updated_at=response.created_at if response is not None else task.created_at,
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


def build_orbit_dashboard(
    session: Session,
    user: HumanUser,
    *,
    heartbeat_interval_seconds: int = 30,
) -> OrbitDashboard:
    from agentpost.control.approval_service import (
        list_human_approval_requests,
        pending_human_approval_count,
    )

    entries = [
        entry for entry in list_agent_access(session, user) if entry.agent.status != "disabled"
    ]
    agent_ids = {entry.agent.id for entry in entries}
    role_map = {entry.agent.id: entry.role for entry in entries}
    entries_by_agent = {entry.agent.id: entry for entry in entries}
    tasks = list_orbit_tasks(session, user, limit=50)
    recent_rows = [
        row
        for row in _message_rows(session, agent_ids=agent_ids, limit=12)
        if _row_visible_after_access_grant(row, entries_by_agent)
    ]
    recent_task_ids = [row[0].id for row in recent_rows if row[0].message_type == "task"]
    recent_task_results = _responses_for_tasks(session, recent_task_ids)
    connector_types = _connector_types_for_agents(session, agent_ids)
    owner_humans = _owner_humans_for_agents(
        session,
        agent_ids | {agent.id for row in recent_rows for agent in row[2:]},
    )
    agents_by_id = {entry.agent.id: entry.agent for entry in entries}
    recent_messages = [
        _orbit_message(
            row,
            role_map=role_map,
            task_results=recent_task_results,
            connector_types=connector_types,
            owner_humans=owner_humans,
            agents_by_id=agents_by_id,
            current_human_id=user.id,
        )
        for row in recent_rows
    ]

    unread_by_agent: dict[UUID, int] = {}
    for entry in entries:
        unread_query = (
            select(func.count(Delivery.id))
            .join(Message, Message.id == Delivery.message_id)
            .where(
                Delivery.recipient_agent_id == entry.agent.id,
                Delivery.delivery_status == "delivered",
            )
        )
        if entry.source == "organization":
            unread_query = unread_query.where(Message.created_at >= entry.granted_at)
        unread_by_agent[entry.agent.id] = int(session.scalar(unread_query) or 0)

    pending_by_agent: dict[UUID, int] = {agent_id: 0 for agent_id in agent_ids}
    task_rows = [
        row
        for row in _task_rows(session, agent_ids=agent_ids, limit=None)
        if _row_visible_after_access_grant(row, entries_by_agent)
    ]
    task_results = _responses_for_tasks(session, [row[0].id for row in task_rows])
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
                is_default=(entry.agent.id == user.default_agent_id),
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
                connection_state=connector_connection_state(
                    connector,
                    now=now,
                    heartbeat_interval_seconds=heartbeat_interval_seconds,
                ),
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
    connected_agent_count = sum(agent.connection_state == "connected" for agent in agents)
    return OrbitDashboard(
        user=human_profile(user),
        metrics=OrbitMetrics(
            agent_count=len(entries),
            connected_agent_count=connected_agent_count,
            online_recently_count=connected_agent_count,
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
