"""Add Human identities and Agent authorization relationships.

Revision ID: 0006_human_control_plane
Revises: 0005_access_control
Create Date: 2026-08-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_human_control_plane"
down_revision: str | None = "0005_access_control"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "human_users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("email = lower(email)", name="ck_human_users_email_lowercase"),
        sa.CheckConstraint(
            "status IN ('active', 'disabled')",
            name="ck_human_users_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "human_access_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("human_user_id", sa.Uuid(), nullable=False),
        sa.Column("key_digest", sa.String(length=64), nullable=False),
        sa.Column("key_prefix", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["human_user_id"], ["human_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_digest"),
    )
    op.create_index(
        "ix_human_access_keys_human_user_id",
        "human_access_keys",
        ["human_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_human_access_keys_key_prefix",
        "human_access_keys",
        ["key_prefix"],
        unique=False,
    )

    op.create_table(
        "agent_ownerships",
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("human_user_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["human_user_id"], ["human_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("agent_id"),
    )
    op.create_index(
        "ix_agent_ownerships_human_user_id",
        "agent_ownerships",
        ["human_user_id"],
        unique=False,
    )

    op.create_table(
        "human_agent_grants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("human_user_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "role IN ('operator', 'viewer', 'auditor')",
            name="ck_human_agent_grants_role",
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["human_user_id"], ["human_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "human_user_id",
            "agent_id",
            name="uq_human_agent_grants_user_agent",
        ),
    )
    op.create_index(
        "ix_human_agent_grants_human_user_id",
        "human_agent_grants",
        ["human_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_human_agent_grants_agent_id",
        "human_agent_grants",
        ["agent_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("human_agent_grants")
    op.drop_table("agent_ownerships")
    op.drop_table("human_access_keys")
    op.drop_table("human_users")
