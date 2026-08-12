from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import SecretStr
from sqlalchemy import Select, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

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
    MessageResponse,
    MessageType,
    Priority,
    ResultPayload,
    TaskPayload,
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
        payload.model_dump(mode="json", by_alias=True, exclude_none=False),
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
    recipient = session.scalar(select(Agent).where(Agent.address == recipient_address))
    if recipient is None or recipient.status != "active":
        raise RecipientNotFoundError(recipient_address)

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
    session.add_all([message, delivery, idempotency, audit])
    try:
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


def get_visible_message(session: Session, *, agent_id: UUID, message_id: str) -> Message:
    message = session.scalar(
        _message_query()
        .join(Delivery, Delivery.message_id == Message.id)
        .where(
            Message.id == message_id,
            or_(Message.sender_agent_id == agent_id, Delivery.recipient_agent_id == agent_id),
        )
    )
    if message is None:
        raise MessageNotFoundError(message_id)
    return message


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
        attachments=[],
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
