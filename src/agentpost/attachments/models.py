from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Table,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agentpost.db import Base
from agentpost.identity.models import Agent, utc_now

if TYPE_CHECKING:
    from agentpost.messaging.models import Message


message_attachments = Table(
    "message_attachments",
    Base.metadata,
    Column(
        "message_id",
        String(64),
        ForeignKey("messages.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "attachment_id",
        Uuid(),
        ForeignKey("attachments.id", ondelete="RESTRICT"),
        primary_key=True,
    ),
    Index("ix_message_attachments_attachment", "attachment_id"),
)


class Attachment(Base):
    __tablename__ = "attachments"
    __table_args__ = (
        CheckConstraint("state IN ('pending', 'attached')", name="ck_attachments_state"),
        CheckConstraint("size >= 0", name="ck_attachments_nonnegative_size"),
        CheckConstraint(
            "(state = 'pending' AND message_id IS NULL) OR "
            "(state = 'attached' AND message_id IS NOT NULL)",
            name="ck_attachments_state_message",
        ),
        Index("ix_attachments_uploader_state", "uploader_agent_id", "state"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    uploader_agent_id: Mapped[UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    message_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    uploader: Mapped[Agent] = relationship(foreign_keys=[uploader_agent_id])
    primary_message: Mapped[Message | None] = relationship(foreign_keys=[message_id])
    messages: Mapped[list[Message]] = relationship(
        secondary="message_attachments",
        viewonly=True,
    )
