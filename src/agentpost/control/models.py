from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agentpost.db import Base
from agentpost.identity.models import utc_now


class HumanUser(Base):
    __tablename__ = "human_users"
    __table_args__ = (
        CheckConstraint("email = lower(email)", name="ck_human_users_email_lowercase"),
        CheckConstraint(
            "status IN ('active', 'disabled')",
            name="ck_human_users_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    access_keys: Mapped[list[HumanAccessKey]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    sessions: Mapped[list[HumanSession]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    organization_memberships: Mapped[list[OrganizationMembership]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    ownerships: Mapped[list[AgentOwnership]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    grants: Mapped[list[HumanAgentGrant]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class HumanAccessKey(Base):
    __tablename__ = "human_access_keys"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    human_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("human_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    key_prefix: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[HumanUser] = relationship(back_populates="access_keys")


class HumanSession(Base):
    __tablename__ = "human_sessions"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    human_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("human_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[HumanUser] = relationship(back_populates="sessions")


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint("slug = lower(slug)", name="ck_organizations_slug_lowercase"),
        CheckConstraint(
            "status IN ('active', 'archived')",
            name="ck_organizations_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(63), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    memberships: Mapped[list[OrganizationMembership]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    agent_assignments: Mapped[list[OrganizationAgent]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        CheckConstraint(
            "role IN ('owner', 'admin', 'member', 'auditor')",
            name="ck_organization_memberships_role",
        ),
        UniqueConstraint(
            "organization_id",
            "human_user_id",
            name="uq_organization_memberships_org_user",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    human_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("human_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    organization: Mapped[Organization] = relationship(back_populates="memberships")
    user: Mapped[HumanUser] = relationship(back_populates="organization_memberships")


class OrganizationAgent(Base):
    __tablename__ = "organization_agents"

    agent_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    organization: Mapped[Organization] = relationship(back_populates="agent_assignments")


class AgentOwnership(Base):
    __tablename__ = "agent_ownerships"

    agent_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    human_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("human_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    user: Mapped[HumanUser] = relationship(back_populates="ownerships")


class HumanAgentGrant(Base):
    __tablename__ = "human_agent_grants"
    __table_args__ = (
        CheckConstraint(
            "role IN ('operator', 'viewer', 'auditor')",
            name="ck_human_agent_grants_role",
        ),
        UniqueConstraint(
            "human_user_id",
            "agent_id",
            name="uq_human_agent_grants_user_agent",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    human_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("human_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    user: Mapped[HumanUser] = relationship(back_populates="grants")
