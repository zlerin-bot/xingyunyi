from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agentpost.db import Base
from agentpost.identity.models import Agent, utc_now


class AccessRule(Base):
    __tablename__ = "access_rules"
    __table_args__ = (
        CheckConstraint("effect IN ('allow', 'block')", name="ck_access_rules_effect"),
        CheckConstraint(
            "subject_type IN ('agent', 'domain')",
            name="ck_access_rules_subject_type",
        ),
        UniqueConstraint(
            "owner_agent_id",
            "effect",
            "subject_type",
            "subject",
            name="uq_access_rules_owner_effect_type_subject",
        ),
        Index("ix_access_rules_owner_subject", "owner_agent_id", "subject_type", "subject"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_agent_id: Mapped[UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    effect: Mapped[str] = mapped_column(String(16), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(16), nullable=False)
    subject: Mapped[str] = mapped_column(String(320), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    owner: Mapped[Agent] = relationship(back_populates="access_rules")
