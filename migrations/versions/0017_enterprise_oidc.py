"""Add enterprise OIDC providers, identities, and one-time login state.

Revision ID: 0017_enterprise_oidc
Revises: 0016_oauth_device_grants
Create Date: 2026-08-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_enterprise_oidc"
down_revision: str | None = "0016_oauth_device_grants"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organization_oidc_providers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("issuer", sa.String(length=1000), nullable=False),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("encrypted_client_secret", sa.String(length=2000), nullable=False),
        sa.Column("scopes", sa.String(length=500), nullable=False),
        sa.Column("authorization_endpoint", sa.String(length=2000), nullable=False),
        sa.Column("token_endpoint", sa.String(length=2000), nullable=False),
        sa.Column("jwks_uri", sa.String(length=2000), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disabled_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('active', 'disabled')",
            name="ck_org_oidc_provider_status",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["human_users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "issuer",
            name="uq_org_oidc_provider_organization_issuer",
        ),
    )
    op.create_index(
        "ix_organization_oidc_providers_organization_id",
        "organization_oidc_providers",
        ["organization_id"],
    )
    op.create_index(
        "ix_organization_oidc_providers_issuer",
        "organization_oidc_providers",
        ["issuer"],
    )
    op.create_index(
        "ix_organization_oidc_providers_status",
        "organization_oidc_providers",
        ["status"],
    )

    op.create_table(
        "organization_oidc_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("subject", sa.String(length=512), nullable=False),
        sa.Column("human_user_id", sa.Uuid(), nullable=False),
        sa.Column("email_at_link", sa.String(length=320), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["provider_id"], ["organization_oidc_providers.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["human_user_id"], ["human_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_id", "subject", name="uq_org_oidc_identity_subject"),
        sa.UniqueConstraint("provider_id", "human_user_id", name="uq_org_oidc_identity_human"),
    )
    op.create_index(
        "ix_organization_oidc_identities_provider_id",
        "organization_oidc_identities",
        ["provider_id"],
    )
    op.create_index(
        "ix_organization_oidc_identities_human_user_id",
        "organization_oidc_identities",
        ["human_user_id"],
    )

    op.create_table(
        "oidc_login_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("state_digest", sa.String(length=64), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("encrypted_code_verifier", sa.String(length=1000), nullable=False),
        sa.Column("nonce_digest", sa.String(length=64), nullable=False),
        sa.Column("link_human_user_id", sa.Uuid()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["provider_id"], ["organization_oidc_providers.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["link_human_user_id"], ["human_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("state_digest"),
    )
    op.create_index("ix_oidc_login_states_provider_id", "oidc_login_states", ["provider_id"])
    op.create_index(
        "ix_oidc_login_states_link_human_user_id",
        "oidc_login_states",
        ["link_human_user_id"],
    )
    op.create_index("ix_oidc_login_states_expires_at", "oidc_login_states", ["expires_at"])


def downgrade() -> None:
    op.drop_table("oidc_login_states")
    op.drop_table("organization_oidc_identities")
    op.drop_table("organization_oidc_providers")
