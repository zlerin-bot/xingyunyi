"""Add Human organizations, memberships, and Agent assignments.

Revision ID: 0008_organizations
Revises: 0007_human_sessions
Create Date: 2026-08-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_organizations"
down_revision: str | None = "0007_human_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=63), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("slug = lower(slug)", name="ck_organizations_slug_lowercase"),
        sa.CheckConstraint(
            "status IN ('active', 'archived')",
            name="ck_organizations_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "organization_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("human_user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "role IN ('owner', 'admin', 'member', 'auditor')",
            name="ck_organization_memberships_role",
        ),
        sa.ForeignKeyConstraint(
            ["human_user_id"],
            ["human_users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "human_user_id",
            name="uq_organization_memberships_org_user",
        ),
    )
    op.create_index(
        "ix_organization_memberships_organization_id",
        "organization_memberships",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_organization_memberships_human_user_id",
        "organization_memberships",
        ["human_user_id"],
        unique=False,
    )
    op.create_table(
        "organization_agents",
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("agent_id"),
    )
    op.create_index(
        "ix_organization_agents_organization_id",
        "organization_agents",
        ["organization_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("organization_agents")
    op.drop_table("organization_memberships")
    op.drop_table("organizations")
