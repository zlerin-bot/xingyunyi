from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from agentpost.control.models import Organization, OrganizationAgent
from agentpost.identity.models import Agent, utc_now
from agentpost.messaging.models import AuditLog, Delivery, IdempotencyRecord, Message
from agentpost.organizations.participants import effective_organization_participants
from agentpost.organizations.schemas import (
    OrganizationChannelAgent,
    OrganizationChannelMessageCreate,
    OrganizationChannelMessageResponse,
    OrganizationChannelSummary,
)


class OrganizationChannelNotFoundError(Exception):
    pass


class OrganizationChannelAmbiguousError(Exception):
    pass


class OrganizationChannelResponderNotFoundError(Exception):
    pass


class OrganizationChannelThreadNotFoundError(Exception):
    pass


class OrganizationChannelIdempotencyConflictError(Exception):
    pass


class OrganizationChannelInvalidIdempotencyKeyError(Exception):
    pass


@dataclass(frozen=True)
class OrganizationChannelSendResult:
    response: OrganizationChannelMessageResponse
    replayed: bool


def get_organization_channel(
    session: Session,
    *,
    sender: Agent,
) -> OrganizationChannelSummary:
    assignment = session.get(OrganizationAgent, sender.id)
    if assignment is not None:
        organization, agents = _organization_and_agents(
            session,
            organization_id=assignment.organization_id,
            sender=sender,
        )
        return _channel_summary(organization, agents)
    channels = list_organization_channels(session, sender=sender)
    if not channels:
        raise OrganizationChannelNotFoundError(str(sender.id))
    if len(channels) > 1:
        raise OrganizationChannelAmbiguousError(str(sender.id))
    return channels[0]


def _channel_summary(
    organization: Organization,
    agents: list[Agent],
) -> OrganizationChannelSummary:
    return OrganizationChannelSummary(
        organization_id=organization.id,
        organization_slug=organization.slug,
        organization_name=organization.name,
        agents=[
            OrganizationChannelAgent(
                agent_id=agent.id,
                address=agent.address,
                handle=agent.handle,
                display_name=agent.display_name,
            )
            for agent in agents
        ],
    )


def list_organization_channels(
    session: Session,
    *,
    sender: Agent,
) -> list[OrganizationChannelSummary]:
    organizations = session.scalars(
        select(Organization)
        .where(Organization.status == "active")
        .order_by(Organization.name, Organization.slug)
    ).all()
    channels: list[OrganizationChannelSummary] = []
    for organization in organizations:
        participants = effective_organization_participants(
            session,
            organization_id=organization.id,
        )
        agents = [participant.agent for participant in participants]
        if sender.id in {agent.id for agent in agents}:
            channels.append(_channel_summary(organization, agents))
    return channels


def _request_hash(organization_id: UUID, payload: OrganizationChannelMessageCreate) -> str:
    canonical = json.dumps(
        {
            "operation": "organization_channel_message",
            "organization_id": str(organization_id),
            "payload": payload.model_dump(mode="json", by_alias=True, exclude_none=False),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _validate_key(value: str) -> str:
    if not value or len(value) > 255 or any(character.isspace() for character in value):
        raise OrganizationChannelInvalidIdempotencyKeyError(value)
    try:
        value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise OrganizationChannelInvalidIdempotencyKeyError(value) from exc
    return value


def _organization_and_agents(
    session: Session,
    *,
    organization_id: UUID,
    sender: Agent,
) -> tuple[Organization, list[Agent]]:
    organization = session.scalar(
        select(Organization).where(
            Organization.id == organization_id,
            Organization.status == "active",
        )
    )
    if organization is None:
        raise OrganizationChannelNotFoundError(str(organization_id))
    participants = effective_organization_participants(
        session,
        organization_id=organization_id,
    )
    agents = [participant.agent for participant in participants]
    if sender.id not in {agent.id for agent in agents}:
        raise OrganizationChannelNotFoundError(str(organization_id))
    return organization, agents


def _event_messages(session: Session, *, thread_id: UUID, event_id: UUID) -> list[Message]:
    messages = list(
        session.scalars(
            select(Message)
            .options(joinedload(Message.delivery))
            .where(Message.thread_id == thread_id)
            .order_by(Message.created_at, Message.id)
        ).unique()
    )
    return [
        message
        for message in messages
        if (message.message_metadata or {}).get("organization_event_id") == str(event_id)
    ]


def _response(
    organization: Organization,
    messages: list[Message],
    *,
    replayed: bool,
) -> OrganizationChannelMessageResponse:
    if not messages:
        raise RuntimeError("organization channel event has no delivery messages")
    first = messages[0]
    metadata = first.message_metadata or {}
    return OrganizationChannelMessageResponse(
        event_id=UUID(str(metadata["organization_event_id"])),
        organization_id=organization.id,
        organization_slug=organization.slug,
        thread_id=first.thread_id,
        reply_to_event_id=(
            UUID(str(metadata["reply_to_event_id"])) if metadata.get("reply_to_event_id") else None
        ),
        sender_agent_id=first.sender_agent_id,
        recipient_agent_ids=[message.delivery.recipient_agent_id for message in messages],
        requested_responder_agent_ids=[
            UUID(str(agent_id)) for agent_id in metadata.get("requested_responder_agent_ids", [])
        ],
        message_ids=[message.id for message in messages],
        created_at=first.created_at,
        replayed=replayed,
    )


def send_organization_channel_message(
    session: Session,
    *,
    organization_id: UUID,
    sender: Agent,
    payload: OrganizationChannelMessageCreate,
    idempotency_key: str,
    request_id: str,
) -> OrganizationChannelSendResult:
    key = _validate_key(idempotency_key)
    request_hash = _request_hash(organization_id, payload)
    organization, agents = _organization_and_agents(
        session,
        organization_id=organization_id,
        sender=sender,
    )
    existing = session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.sender_agent_id == sender.id,
            IdempotencyRecord.idempotency_key == key,
        )
    )
    if existing is not None:
        if existing.request_hash != request_hash:
            raise OrganizationChannelIdempotencyConflictError(key)
        first = session.get(Message, existing.message_id)
        if first is None:
            raise RuntimeError("idempotency record references a missing channel message")
        event_id = UUID(str(first.message_metadata["organization_event_id"]))
        messages = _event_messages(session, thread_id=first.thread_id, event_id=event_id)
        return OrganizationChannelSendResult(
            response=_response(organization, messages, replayed=True),
            replayed=True,
        )

    assigned_ids = {agent.id for agent in agents}
    requested_ids = set(payload.requested_responder_agent_ids)
    if sender.id in requested_ids or not requested_ids.issubset(assigned_ids):
        raise OrganizationChannelResponderNotFoundError(
            "requested responder is not in organization"
        )

    parent_message: Message | None = None
    if payload.thread_id is not None and payload.reply_to_event_id is not None:
        parent_messages = _event_messages(
            session,
            thread_id=payload.thread_id,
            event_id=payload.reply_to_event_id,
        )
        if not parent_messages or (parent_messages[0].message_metadata or {}).get(
            "organization_id"
        ) != str(organization.id):
            raise OrganizationChannelThreadNotFoundError(str(payload.thread_id))
        parent_message = parent_messages[0]

    recipients = [agent for agent in agents if agent.id != sender.id]
    if not recipients:
        recipients = [sender]
    now = utc_now()
    event_id = uuid4()
    thread_id = payload.thread_id or uuid4()
    metadata = dict(payload.metadata)
    metadata.update(
        {
            "channel_scope": "organization",
            "organization_id": str(organization.id),
            "organization_slug": organization.slug,
            "organization_name": organization.name,
            "organization_event_id": str(event_id),
            "reply_to_event_id": (
                str(payload.reply_to_event_id) if payload.reply_to_event_id else None
            ),
            "requested_responder_agent_ids": [
                str(agent_id) for agent_id in payload.requested_responder_agent_ids
            ],
            "requested_responder_addresses": [
                agent.address for agent in agents if agent.id in requested_ids
            ],
            "organization_recipient_count": len(recipients),
            "reply_policy": "addressed_agents_reply",
            "context_visible_to_all_assigned_agents": True,
        }
    )
    messages: list[Message] = []
    deliveries: list[Delivery] = []
    for recipient in recipients:
        message = Message(
            id=f"msg_{uuid4().hex}",
            sender_agent_id=sender.id,
            subject=payload.subject,
            content_format=payload.content.format,
            content_body=payload.content.body,
            message_type=payload.message_type.value,
            priority=payload.priority.value,
            thread_id=thread_id,
            reply_to_message_id=parent_message.id if parent_message is not None else None,
            requires_ack=payload.requires_ack,
            task_payload=(payload.task.model_dump(mode="json") if payload.task else None),
            result_payload=(payload.result.model_dump(mode="json") if payload.result else None),
            message_metadata=metadata,
            accepted_at=now,
            created_at=now,
            expires_at=None,
        )
        delivery = Delivery(
            message=message,
            recipient_agent_id=recipient.id,
            delivery_status="delivered",
            delivery_attempts=1,
            last_attempt_at=now,
            delivered_at=now,
            created_at=now,
        )
        messages.append(message)
        deliveries.append(delivery)

    session.add_all([*messages, *deliveries])
    try:
        session.flush()
        session.add_all(
            [
                IdempotencyRecord(
                    sender_agent_id=sender.id,
                    idempotency_key=key,
                    request_hash=request_hash,
                    operation="organization_channel_message",
                    message_id=messages[0].id,
                    created_at=now,
                ),
                AuditLog(
                    actor_agent_id=sender.id,
                    action="organization_channel.message_accepted",
                    target_type="organization_channel_event",
                    target_id=str(event_id),
                    outcome="success",
                    request_id=request_id,
                    audit_metadata={
                        "organization_id": str(organization.id),
                        "recipient_count": len(recipients),
                        "requested_responder_count": len(requested_ids),
                    },
                    created_at=now,
                ),
            ]
        )
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.sender_agent_id == sender.id,
                IdempotencyRecord.idempotency_key == key,
            )
        )
        if existing is None or existing.request_hash != request_hash:
            raise OrganizationChannelIdempotencyConflictError(key) from None
        first = session.get(Message, existing.message_id)
        if first is None:
            raise RuntimeError("idempotency replay channel message is missing") from None
        replay_event_id = UUID(str(first.message_metadata["organization_event_id"]))
        replay_messages = _event_messages(
            session,
            thread_id=first.thread_id,
            event_id=replay_event_id,
        )
        return OrganizationChannelSendResult(
            response=_response(organization, replay_messages, replayed=True),
            replayed=True,
        )

    stored = _event_messages(session, thread_id=thread_id, event_id=event_id)
    return OrganizationChannelSendResult(
        response=_response(organization, stored, replayed=False),
        replayed=False,
    )
