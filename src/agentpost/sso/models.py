from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from agentpost.db import Base
from agentpost.identity.models import utc_now


class OrganizationOidcProvider(Base):
    __tablename__ = "organization_oidc_providers"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'disabled')", name="ck_org_oidc_provider_status"),
        UniqueConstraint(
            "organization_id",
            "issuer",
            name="uq_org_oidc_provider_organization_issuer",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    issuer: Mapped[str] = mapped_column(String(1000), nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_client_secret: Mapped[str] = mapped_column(String(2000), nullable=False)
    scopes: Mapped[str] = mapped_column(String(500), nullable=False, default="openid email profile")
    authorization_endpoint: Mapped[str] = mapped_column(String(2000), nullable=False)
    token_endpoint: Mapped[str] = mapped_column(String(2000), nullable=False)
    jwks_uri: Mapped[str] = mapped_column(String(2000), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", index=True)
    created_by_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("human_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OrganizationOidcIdentity(Base):
    __tablename__ = "organization_oidc_identities"
    __table_args__ = (
        UniqueConstraint("provider_id", "subject", name="uq_org_oidc_identity_subject"),
        UniqueConstraint(
            "provider_id",
            "human_user_id",
            name="uq_org_oidc_identity_human",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    provider_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organization_oidc_providers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject: Mapped[str] = mapped_column(String(512), nullable=False)
    human_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("human_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email_at_link: Mapped[str] = mapped_column(String(320), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OidcLoginState(Base):
    __tablename__ = "oidc_login_states"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    state_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    provider_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organization_oidc_providers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    encrypted_code_verifier: Mapped[str] = mapped_column(String(1000), nullable=False)
    nonce_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    link_human_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("human_users.id", ondelete="CASCADE"),
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
