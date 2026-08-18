"""Add organization DNS domain verification.

Revision ID: 0014_organization_domain_verification
Revises: 0013_organization_self_governance
Create Date: 2026-08-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_organization_domain_verification"
down_revision: str | None = "0013_organization_self_governance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organization_domains",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("domain", sa.String(length=253), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("verification_digest", sa.String(length=64), nullable=False),
        sa.Column("verification_prefix", sa.String(length=32), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("domain = lower(domain)", name="ck_organization_domains_lowercase"),
        sa.CheckConstraint(
            "status IN ('pending', 'verified', 'revoked')",
            name="ck_organization_domains_status",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["human_users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_organization_domains_organization_id",
        "organization_domains",
        ["organization_id"],
    )
    op.create_index(
        "ix_organization_domains_domain",
        "organization_domains",
        ["domain"],
        unique=True,
    )
    op.create_index(
        "ix_organization_domains_status",
        "organization_domains",
        ["status"],
    )


def downgrade() -> None:
    op.drop_table("organization_domains")
