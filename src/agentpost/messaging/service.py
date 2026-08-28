from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import SecretStr
from sqlalchemy import Select, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from agentpost.access.service import (
    DeliveryNotAllowedError,
    lock_recipient_for_delivery,
    record_delivery_denied,
)
from agentpost.attachments.service import (
    attachment_metadata,
    bind_attachments,
)
from agentpost.control.models import AgentOwnership, HumanThreadArchive
from agentpost.identity.models import Agent, utc_now
from agentpost.messaging.cursors import (
    InboxCursor,
    decode_cursor,
    encode_cursor,
    normalized_filter_hash,
)
from agentpost.messaging.models import AuditLog, Delivery, IdempotencyRecord, Message
from agentpost.messaging.schemas import (
    AgentReference,
    ContentResponse,
    DeliveryResponse,
    InboxResponse,
    InboxStatus,
    MessageCreate,
    MessageReply,
    MessageResponse,
    MessageType,
    Priority,
    ResultPayload,
    TaskPayload,
    ThreadListResponse,
    ThreadResponse,
    ThreadSummary,
)

_IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[\x21-\x7e]{1,255}$", flags=re.ASCII)


class RecipientNotFoundError(Exception):
    pass


class MessageNotFoundError(Exception):
    pass


class InvalidIdempotencyKeyError(ValueError):
    pass


class IdempotencyConflictError(Exception):
    pass


class InvalidStateTransitionError(Exception):
    pass


@dataclass(frozen=True)
class SendResult:
    message: Message
    replayed: bool


@dataclass(frozen=True)
class InboxFilters:
    status: InboxStatus | None = None
    sender: str | None = None
    message_type: MessageType | None = None
    priority: Priority | None = None
    since: datetime | None = None

    def canonical(self) -> dict[str, str | None]:
        return {
            "status": self.status.value if self.status else None,
            "sender": self.sender,
            "type": self.message_type.value if self.message_type else None,
            "priority": self.priority.value if self.priority else None,
            "since": self.since.isoformat() if self.since else None,
        }


def _request_hash(payload: MessageCreate) -> str:
    canonical = json.dumps(
        {
            "operation": "send_message",
            "payload": payload.model_dump(mode="json", by_alias=True, exclude_none=False),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _reply_request_hash(message_id: str, payload: MessageReply) -> str:
    canonical = json.dumps(
        {
            "operation": "reply_message",
            "reply_to": message_id,
            "payload": payload.model_dump(mode="json", by_alias=True, exclude_none=False),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _validate_idempotency_key(value: str) -> str:
    if not _IDEMPOTENCY_KEY_PATTERN.fullmatch(value):
        raise InvalidIdempotencyKeyError(
            "Idempotency-Key must contain 1-255 printable ASCII characters without spaces"
        )
    return value


def _message_query() -> Select[tuple[Message]]:
    return select(Message).options(
        joinedload(Message.sender),
        joinedload(Message.delivery).joinedload(Delivery.recipient),
        selectinload(Message.attachments),
    )


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _load_message(session: Session, message_id: str) -> Message | None:
    return session.scalar(_message_query().where(Message.id == message_id))


def send_message(
    session: Session,
    *,
    sender: Agent,
    payload: MessageCreate,
    idempotency_key: str,
    request_id: str,
) -> SendResult:
    key = _validate_idempotency_key(idempotency_key)
    request_hash = _request_hash(payload)
    existing = session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.sender_agent_id == sender.id,
            IdempotencyRecord.idempotency_key == key,
        )
    )
    if existing is not None:
        if existing.request_hash != request_hash:
            raise IdempotencyConflictError(key)
        message = _load_message(session, existing.message_id)
        if message is None:  # Defensive: the foreign key should make this impossible.
            raise RuntimeError("idempotency record references a missing message")
        return SendResult(message=message, replayed=True)

    recipient_address = payload.to[0].address
    try:
        recipient = lock_recipient_for_delivery(
            session,
            sender=sender,
            recipient_address=recipient_address,
        )
    except LookupError:
        raise RecipientNotFoundError(recipient_address) from None
    except DeliveryNotAllowedError as exc:
        record_delivery_denied(
            session,
            sender=sender,
            error=exc,
            request_id=request_id,
        )
        raise

    now = utc_now()
    message = Message(
        id=f"msg_{uuid4().hex}",
        sender_agent_id=sender.id,
        subject=payload.subject,
        content_format=payload.content.format,
        content_body=payload.content.body,
        message_type=payload.message_type.value,
        priority=payload.priority.value,
        thread_id=uuid4(),
        reply_to_message_id=None,
        requires_ack=payload.requires_ack,
        task_payload=(payload.task.model_dump(mode="json") if payload.task else None),
        result_payload=None,
        message_metadata=payload.metadata,
        accepted_at=now,
        created_at=now,
        expires_at=payload.expires_at,
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
    idempotency = IdempotencyRecord(
        sender_agent_id=sender.id,
        idempotency_key=key,
        request_hash=request_hash,
        operation="send_message",
        message_id=message.id,
        created_at=now,
    )
    audit = AuditLog(
        actor_agent_id=sender.id,
        action="message.accepted",
        target_type="message",
        target_id=message.id,
        outcome="success",
        request_id=request_id,
        audit_metadata={
            "recipient_agent_id": str(recipient.id),
            "message_type": message.message_type,
        },
        created_at=now,
    )
    # Flush the message/delivery graph before the sender-scoped idempotency row.
    # SQLite commonly runs without foreign-key enforcement, but PostgreSQL checks
    # the idempotency_records.message_id FK immediately.  Explicit staging keeps
    # the whole operation in one transaction while making the dependency order
    # unambiguous to every supported database.
    session.add_all([message, delivery])
    try:
        session.flush()
        bind_attachments(
            session,
            sender=sender,
            attachment_ids=payload.attachments,
            message_id=message.id,
        )
        session.add_all([idempotency, audit])
        session.flush()
        session.commit()
    except IntegrityError:
        session.rollback()
        # This is the concurrent retry path for the sender-scoped unique key.
        existing = session.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.sender_agent_id == sender.id,
                IdempotencyRecord.idempotency_key == key,
            )
        )
        if existing is None:
            raise
        if existing.request_hash != request_hash:
            raise IdempotencyConflictError(key) from None
        replay = _load_message(session, existing.message_id)
        if replay is None:
            raise RuntimeError("idempotency replay message is missing") from None
        return SendResult(message=replay, replayed=True)

    stored = _load_message(session, message.id)
    if stored is None:
        raise RuntimeError("committed message could not be reloaded")
    return SendResult(message=stored, replayed=False)


def reply_to_message(
    session: Session,
    *,
    sender: Agent,
    parent_message_id: str,
    payload: MessageReply,
    idempotency_key: str,
    request_id: str,
) -> SendResult:
    key = _validate_idempotency_key(idempotency_key)
    request_hash = _reply_request_hash(parent_message_id, payload)
    existing = session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.sender_agent_id == sender.id,
            IdempotencyRecord.idempotency_key == key,
        )
    )
    if existing is not None:
        if existing.request_hash != request_hash:
            raise IdempotencyConflictError(key)
        replay = _load_message(session, existing.message_id)
        if replay is None:
            raise RuntimeError("idempotency record references a missing reply")
        return SendResult(message=replay, replayed=True)

    parent = get_visible_message(session, agent_id=sender.id, message_id=parent_message_id)
    if payload.message_type == MessageType.result and parent.message_type != MessageType.task.value:
        raise InvalidStateTransitionError(parent.message_type)
    if sender.id == parent.sender_agent_id:
        recipient_id = parent.delivery.recipient_agent_id
    elif sender.id == parent.delivery.recipient_agent_id:
        recipient_id = parent.sender_agent_id
    else:  # Defensive; get_visible_message already enforces this.
        raise MessageNotFoundError(parent_message_id)
    try:
        recipient = lock_recipient_for_delivery(
            session,
            sender=sender,
            recipient_id=recipient_id,
        )
    except LookupError:
        raise RecipientNotFoundError(str(recipient_id)) from None
    except DeliveryNotAllowedError as exc:
        record_delivery_denied(
            session,
            sender=sender,
            error=exc,
            request_id=request_id,
        )
        raise

    now = utc_now()
    message = Message(
        id=f"msg_{uuid4().hex}",
        sender_agent_id=sender.id,
        subject=payload.subject,
        content_format=payload.content.format,
        content_body=payload.content.body,
        message_type=payload.message_type.value,
        priority=payload.priority.value,
        thread_id=parent.thread_id,
        reply_to_message_id=parent.id,
        requires_ack=payload.requires_ack,
        task_payload=(payload.task.model_dump(mode="json") if payload.task else None),
        result_payload=(payload.result.model_dump(mode="json") if payload.result else None),
        message_metadata=payload.metadata,
        accepted_at=now,
        created_at=now,
        expires_at=payload.expires_at,
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
    idempotency = IdempotencyRecord(
        sender_agent_id=sender.id,
        idempotency_key=key,
        request_hash=request_hash,
        operation="reply_message",
        message_id=message.id,
        created_at=now,
    )
    audit = AuditLog(
        actor_agent_id=sender.id,
        action="message.replied",
        target_type="message",
        target_id=message.id,
        outcome="success",
        request_id=request_id,
        audit_metadata={
            "recipient_agent_id": str(recipient.id),
            "reply_to_message_id": parent.id,
            "thread_id": str(parent.thread_id),
            "message_type": message.message_type,
        },
        created_at=now,
    )
    session.add_all([message, delivery])
    try:
        session.flush()
        bind_attachments(
            session,
            sender=sender,
            attachment_ids=payload.attachments,
            message_id=message.id,
        )
        session.add_all([idempotency, audit])
        session.flush()
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.sender_agent_id == sender.id,
                IdempotencyRecord.idempotency_key == key,
            )
        )
        if existing is None:
            raise
        if existing.request_hash != request_hash:
            raise IdempotencyConflictError(key) from None
        replay = _load_message(session, existing.message_id)
        if replay is None:
            raise RuntimeError("idempotency replay reply is missing") from None
        return SendResult(message=replay, replayed=True)

    stored = _load_message(session, message.id)
    if stored is None:
        raise RuntimeError("committed reply could not be reloaded")
    return SendResult(message=stored, replayed=False)


def get_visible_message(session: Session, *, agent_id: UUID, message_id: str) -> Message:
    message = session.scalar(
        _message_query()
        .join(Delivery, Delivery.message_id == Message.id)
        .where(
            Message.id == message_id,
            or_(Message.sender_agent_id == agent_id, Delivery.recipient_agent_id == agent_id),
            Message.thread_id.not_in(_archived_thread_ids_for_agent(agent_id)),
        )
    )
    if message is None:
        raise MessageNotFoundError(message_id)
    return message


def transition_delivery(
    session: Session,
    *,
    recipient: Agent,
    message_id: str,
    transition: str,
    request_id: str,
) -> Message:
    """Apply an explicit recipient transition with monotonic conditional updates."""

    if transition not in {"read", "ack"}:
        raise ValueError("unsupported delivery transition")

    get_visible_message(session, agent_id=recipient.id, message_id=message_id)

    now = utc_now()
    if transition == "read":
        result = session.execute(
            update(Delivery)
            .where(
                Delivery.message_id == message_id,
                Delivery.recipient_agent_id == recipient.id,
                Delivery.delivery_status == "delivered",
            )
            .values(
                delivery_status="read",
                read_at=func.coalesce(Delivery.read_at, now),
            )
        )
    else:
        result = session.execute(
            update(Delivery)
            .where(
                Delivery.message_id == message_id,
                Delivery.recipient_agent_id == recipient.id,
                Delivery.delivery_status.in_(("delivered", "read")),
            )
            .values(
                delivery_status="acked",
                read_at=func.coalesce(Delivery.read_at, now),
                acked_at=func.coalesce(Delivery.acked_at, now),
            )
        )
    changed = result.rowcount == 1

    delivery = session.scalar(
        select(Delivery).where(
            Delivery.message_id == message_id,
            Delivery.recipient_agent_id == recipient.id,
        )
    )
    if delivery is None:
        session.rollback()
        raise MessageNotFoundError(message_id)

    allowed_current_states = {"read", "acked"} if transition == "read" else {"acked"}
    if not changed and delivery.delivery_status not in allowed_current_states:
        session.rollback()
        raise InvalidStateTransitionError(delivery.delivery_status)

    if changed:
        session.add(
            AuditLog(
                actor_agent_id=recipient.id,
                action=f"message.{transition}",
                target_type="message",
                target_id=message_id,
                outcome="success",
                request_id=request_id,
                audit_metadata={"delivery_id": str(delivery.id)},
                created_at=now,
            )
        )
        try:
            session.commit()
        except Exception:
            session.rollback()
            raise

    message = _load_message(session, message_id)
    if message is None:
        raise MessageNotFoundError(message_id)
    return message


def _archived_thread_ids_for_agent(agent_id: UUID):
    return (
        select(HumanThreadArchive.thread_id)
        .join(
            AgentOwnership,
            AgentOwnership.human_user_id == HumanThreadArchive.human_user_id,
        )
        .where(AgentOwnership.agent_id == agent_id)
    )


def _visible_thread_ids(session: Session, agent_id: UUID) -> list[UUID]:
    return list(
        session.scalars(
            select(Message.thread_id)
            .join(Delivery, Delivery.message_id == Message.id)
            .where(
                or_(
                    Message.sender_agent_id == agent_id,
                    Delivery.recipient_agent_id == agent_id,
                ),
                Message.thread_id.not_in(_archived_thread_ids_for_agent(agent_id)),
            )
            .distinct()
        )
    )


def _thread_messages(session: Session, thread_id: UUID, *, agent_id: UUID) -> list[Message]:
    messages = list(
        session.scalars(
            _message_query()
            .where(Message.thread_id == thread_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
        ).unique()
    )
    deduplicated: list[Message] = []
    channel_events: dict[str, Message] = {}
    for message in messages:
        event_id = (message.message_metadata or {}).get("organization_event_id")
        if not event_id:
            deduplicated.append(message)
            continue
        current = channel_events.get(str(event_id))
        if current is None or message.delivery.recipient_agent_id == agent_id:
            channel_events[str(event_id)] = message
    deduplicated.extend(channel_events.values())
    deduplicated.sort(key=lambda item: (item.created_at, item.id))
    return deduplicated


def _thread_participants(messages: list[Message]) -> list[AgentReference]:
    by_id: dict[UUID, AgentReference] = {}
    for message in messages:
        by_id[message.sender.id] = AgentReference(
            agent_id=message.sender.id,
            address=message.sender.address,
        )
        recipient = message.delivery.recipient
        by_id[recipient.id] = AgentReference(
            agent_id=recipient.id,
            address=recipient.address,
        )
    return sorted(by_id.values(), key=lambda item: item.address)


def list_threads(session: Session, *, agent: Agent) -> ThreadListResponse:
    summaries: list[ThreadSummary] = []
    for thread_id in _visible_thread_ids(session, agent.id):
        messages = _thread_messages(session, thread_id, agent_id=agent.id)
        if not messages:
            continue
        last = messages[-1]
        unread_count = sum(
            1
            for message in messages
            if message.delivery.recipient_agent_id == agent.id
            and message.delivery.delivery_status == "delivered"
            and message.delivery.read_at is None
        )
        summaries.append(
            ThreadSummary(
                thread_id=thread_id,
                participants=_thread_participants(messages),
                last_message_at=_as_utc(last.created_at),
                last_message_id=last.id,
                message_count=len(messages),
                unread_count=unread_count,
            )
        )
    summaries.sort(
        key=lambda item: (item.last_message_at, item.last_message_id),
        reverse=True,
    )
    return ThreadListResponse(items=summaries)


def get_thread(session: Session, *, agent: Agent, thread_id: UUID) -> ThreadResponse:
    if thread_id not in set(_visible_thread_ids(session, agent.id)):
        raise MessageNotFoundError(str(thread_id))
    messages = _thread_messages(session, thread_id, agent_id=agent.id)
    if not messages:
        raise MessageNotFoundError(str(thread_id))
    return ThreadResponse(
        thread_id=thread_id,
        participants=_thread_participants(messages),
        messages=[message_response(message) for message in messages],
    )


def list_inbox(
    session: Session,
    *,
    recipient: Agent,
    filters: InboxFilters,
    limit: int,
    cursor_token: str | None,
    cursor_secret: SecretStr,
) -> InboxResponse:
    filter_hash = normalized_filter_hash(filters.canonical())
    after_seq = 0
    if cursor_token:
        after_seq = decode_cursor(
            cursor_token,
            secret=cursor_secret,
            expected_agent_id=recipient.id,
            expected_filter_hash=filter_hash,
        ).inbox_seq

    query = (
        _message_query()
        .join(Delivery, Delivery.message_id == Message.id)
        .where(
            Delivery.recipient_agent_id == recipient.id,
            Delivery.inbox_seq > after_seq,
            Message.thread_id.not_in(_archived_thread_ids_for_agent(recipient.id)),
        )
        .order_by(Delivery.inbox_seq.asc())
        .limit(limit + 1)
    )
    if filters.status == InboxStatus.unread:
        query = query.where(
            Delivery.delivery_status == "delivered",
            Delivery.read_at.is_(None),
            Delivery.acked_at.is_(None),
        )
    elif filters.status is not None:
        query = query.where(Delivery.delivery_status == filters.status.value)
    if filters.sender:
        query = query.where(Message.sender.has(Agent.address == filters.sender))
    if filters.message_type:
        query = query.where(Message.message_type == filters.message_type.value)
    if filters.priority:
        query = query.where(Message.priority == filters.priority.value)
    if filters.since:
        query = query.where(Message.created_at >= filters.since)

    messages = list(session.scalars(query).unique())
    has_more = len(messages) > limit
    page = messages[:limit]
    next_cursor = None
    if page:
        next_cursor = encode_cursor(
            InboxCursor(
                agent_id=recipient.id,
                filter_hash=filter_hash,
                inbox_seq=page[-1].delivery.inbox_seq,
            ),
            cursor_secret,
        )
    return InboxResponse(
        items=[message_response(message) for message in page],
        next_cursor=next_cursor,
        has_more=has_more,
    )


def message_response(message: Message) -> MessageResponse:
    delivery = message.delivery
    recipient = delivery.recipient
    task = TaskPayload.model_validate(message.task_payload) if message.task_payload else None
    result = (
        ResultPayload.model_validate(message.result_payload) if message.result_payload else None
    )
    return MessageResponse(
        message_id=message.id,
        sender=AgentReference(agent_id=message.sender.id, address=message.sender.address),
        to=[AgentReference(agent_id=recipient.id, address=recipient.address)],
        message_type=MessageType(message.message_type),
        subject=message.subject,
        content=ContentResponse(format=message.content_format, body=message.content_body),
        task=task,
        result=result,
        attachments=[attachment_metadata(item) for item in message.attachments],
        thread_id=message.thread_id,
        reply_to=message.reply_to_message_id,
        priority=Priority(message.priority),
        requires_ack=message.requires_ack,
        metadata=message.message_metadata,
        created_at=_as_utc(message.created_at),
        accepted_at=_as_utc(message.accepted_at),
        expires_at=_as_utc(message.expires_at),
        delivery=DeliveryResponse(
            delivery_id=delivery.id,
            recipient_agent_id=delivery.recipient_agent_id,
            inbox_seq=delivery.inbox_seq,
            status=delivery.delivery_status,
            delivery_attempts=delivery.delivery_attempts,
            delivered_at=_as_utc(delivery.delivered_at),
            read_at=_as_utc(delivery.read_at),
            acked_at=_as_utc(delivery.acked_at),
            error=delivery.error,
        ),
    )
