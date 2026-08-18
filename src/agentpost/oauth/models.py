from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from agentpost.db import Base
from agentpost.identity.models import utc_now


class OAuthAccessToken(Base):
    __tablename__ = "oauth_access_tokens"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    token_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    token_prefix: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    agent_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    human_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("human_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connector_instance_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("connector_instances.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pairing_session_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agent_pairing_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    refresh_family_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(1000), nullable=False)
    resource: Mapped[str] = mapped_column(String(1000), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OAuthRefreshToken(Base):
    __tablename__ = "oauth_refresh_tokens"
    __table_args__ = (
        CheckConstraint(
            "revocation_reason IN ('rotated', 'replayed', 'connector_replaced', "
            "'connector_revoked') OR revocation_reason IS NULL",
            name="ck_oauth_refresh_tokens_revocation_reason",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    token_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    token_prefix: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    family_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    agent_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    human_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("human_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connector_instance_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("connector_instances.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pairing_session_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agent_pairing_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    client_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(1000), nullable=False)
    resource: Mapped[str] = mapped_column(String(1000), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
