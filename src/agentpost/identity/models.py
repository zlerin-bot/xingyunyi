from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agentpost.db import Base

if TYPE_CHECKING:
    from agentpost.access.models import AccessRule


def utc_now() -> datetime:
    return datetime.now(UTC)


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (
        CheckConstraint("address = lower(address)", name="ck_agents_address_lowercase"),
        CheckConstraint("domain = lower(domain)", name="ck_agents_domain_lowercase"),
        CheckConstraint(
            "status IN ('active', 'suspended', 'disabled')",
            name="ck_agents_status",
        ),
        CheckConstraint(
            "inbound_policy IN ('public', 'allowlist', 'contacts_only', 'private')",
            name="ck_agents_inbound_policy",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    address: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    inbound_policy: Mapped[str] = mapped_column(String(32), nullable=False, default="public")
    public_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    capabilities: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    endpoint: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    api_keys: Mapped[list[AgentApiKey]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    access_rules: Mapped[list[AccessRule]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def public_attributes(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "address": self.address,
            "display_name": self.display_name,
            "description": self.description,
            "domain": self.domain,
            "status": self.status,
            "public_key": self.public_key,
            "capabilities": list(self.capabilities),
            "endpoint": self.endpoint,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_seen_at": self.last_seen_at,
        }


class AgentApiKey(Base):
    __tablename__ = "agent_api_keys"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    agent_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connector_instance_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("connector_instances.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )
    key_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    key_prefix: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    agent: Mapped[Agent] = relationship(back_populates="api_keys")
