"""Add agent identities and API-key credentials.

Revision ID: 0002_agent_identity
Revises: 0001_service_baseline
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_agent_identity"
down_revision: str | None = "0001_service_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("address", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.String(length=255), nullable=True),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("public_key", sa.Text(), nullable=True),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("endpoint", sa.String(length=2048), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("address = lower(address)", name="ck_agents_address_lowercase"),
        sa.CheckConstraint("domain = lower(domain)", name="ck_agents_domain_lowercase"),
        sa.CheckConstraint(
            "status IN ('active', 'suspended', 'disabled')",
            name="ck_agents_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("address"),
    )
    op.create_index(op.f("ix_agents_domain"), "agents", ["domain"], unique=False)

    op.create_table(
        "agent_api_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("key_digest", sa.String(length=64), nullable=False),
        sa.Column("key_prefix", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_digest"),
    )
    op.create_index(
        op.f("ix_agent_api_keys_agent_id"), "agent_api_keys", ["agent_id"], unique=False
    )
    op.create_index(
        op.f("ix_agent_api_keys_key_prefix"), "agent_api_keys", ["key_prefix"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_api_keys_key_prefix"), table_name="agent_api_keys")
    op.drop_index(op.f("ix_agent_api_keys_agent_id"), table_name="agent_api_keys")
    op.drop_table("agent_api_keys")
    op.drop_index(op.f("ix_agents_domain"), table_name="agents")
    op.drop_table("agents")
