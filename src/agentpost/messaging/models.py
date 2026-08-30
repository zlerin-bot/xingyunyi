from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agentpost.db import Base
from agentpost.identity.models import Agent, utc_now

if TYPE_CHECKING:
    from agentpost.attachments.models import Attachment


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(
            "message_type IN ('message', 'task', 'result', 'request', 'response', "
            "'notification', 'event', 'error', 'system')",
            name="ck_messages_type",
        ),
        CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'urgent')",
            name="ck_messages_priority",
        ),
        Index("ix_messages_thread_created", "thread_id", "created_at", "id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    sender_agent_id: Mapped[UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    content_format: Mapped[str] = mapped_column(String(32), nullable=False)
    content_body: Mapped[Any] = mapped_column(JSON, nullable=False)
    message_type: Mapped[str] = mapped_column(String(32), nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="normal")
    thread_id: Mapped[UUID] = mapped_column(nullable=False, index=True, default=uuid4)
    reply_to_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    requires_ack: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    task_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    message_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, index=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sender: Mapped[Agent] = relationship(foreign_keys=[sender_agent_id])
    delivery: Mapped[Delivery] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        uselist=False,
    )
    attachments: Mapped[list[Attachment]] = relationship(
        secondary="message_attachments",
        viewonly=True,
    )


class Delivery(Base):
    __tablename__ = "deliveries"
    __table_args__ = (
        UniqueConstraint("id", name="uq_deliveries_id"),
        UniqueConstraint(
            "message_id", "recipient_agent_id", name="uq_deliveries_message_recipient"
        ),
        CheckConstraint(
            "delivery_status IN ('accepted', 'delivered', 'read', 'acked', "
            "'failed', 'expired', 'rejected')",
            name="ck_deliveries_status",
        ),
        CheckConstraint(
            "acked_at IS NULL OR read_at IS NOT NULL",
            name="ck_deliveries_ack_implies_read",
        ),
        Index("ix_deliveries_recipient_seq", "recipient_agent_id", "inbox_seq"),
        Index(
            "ix_deliveries_recipient_status_seq",
            "recipient_agent_id",
            "delivery_status",
            "inbox_seq",
        ),
    )

    # SQLite only auto-increments columns whose declared type is exactly INTEGER.
    # PostgreSQL uses BIGINT/BIGSERIAL through the dialect variant.
    inbox_seq: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    id: Mapped[UUID] = mapped_column(nullable=False, default=uuid4)
    message_id: Mapped[str] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recipient_agent_id: Mapped[UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    delivery_status: Mapped[str] = mapped_column(String(32), nullable=False)
    delivery_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    message: Mapped[Message] = relationship(back_populates="delivery")
    recipient: Mapped[Agent] = relationship(foreign_keys=[recipient_agent_id])


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint("sender_agent_id", "idempotency_key", name="uq_idempotency_sender_key"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    sender_agent_id: Mapped[UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    operation: Mapped[str] = mapped_column(String(32), nullable=False, default="send_message")
    message_id: Mapped[str] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_actor_created", "actor_agent_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    actor_agent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[str] = mapped_column(String(255), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    audit_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
