from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from agentpost.db import Base
from agentpost.identity.models import utc_now


class ConnectorInstance(Base):
    """A replaceable tool-host connection for one stable Agent identity."""

    __tablename__ = "connector_instances"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'replaced', 'revoked')",
            name="ck_connector_instances_status",
        ),
        CheckConstraint(
            "health_status IN ('unknown', 'healthy', 'degraded', 'error')",
            name="ck_connector_instances_health_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    connector_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    agent_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    human_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("human_users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    connector_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    device_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    client_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", index=True)
    health_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="unknown", index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    last_error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    credential_rotated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)


class AgentConnectorBinding(Base):
    """The single current Connector for an Agent."""

    __tablename__ = "agent_connector_bindings"

    agent_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    connector_instance_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("connector_instances.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    bound_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class AgentPairingSession(Base):
    """Short-lived device authorization state; never stores the raw device code."""

    __tablename__ = "agent_pairing_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'denied', 'expired', 'consumed')",
            name="ck_agent_pairing_sessions_status",
        ),
        UniqueConstraint(
            "decided_by_human_id",
            "decision_idempotency_key",
            name="uq_pairing_sessions_human_idempotency",
        ),
        CheckConstraint(
            "credential_mode IN ('agent_api_key', 'oauth')",
            name="ck_agent_pairing_sessions_credential_mode",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    pairing_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    device_code_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    user_code_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    user_code_hint: Mapped[str] = mapped_column(String(16), nullable=False)
    connector_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    connector_display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    device_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    client_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    requested_capabilities: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    credential_mode: Mapped[str] = mapped_column(
        String(32), nullable=False, default="agent_api_key"
    )
    oauth_client_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    oauth_scope: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    oauth_resource: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    credential_delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by_human_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("human_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    human_session_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("human_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    agent_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    connector_instance_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("connector_instances.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )
    decision_idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    decision_request_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
