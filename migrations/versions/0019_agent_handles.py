"""Add optional globally unique Agent handles.

Revision ID: 0019_agent_handles
Revises: 0018_rate_limit_buckets
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019_agent_handles"
down_revision: str | None = "0018_rate_limit_buckets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("handle", sa.String(length=32), nullable=True))
    op.create_check_constraint(
        "ck_agents_handle_lowercase",
        "agents",
        "handle IS NULL OR handle = lower(handle)",
    )
    op.create_index("ix_agents_handle", "agents", ["handle"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_agents_handle", table_name="agents")
    op.drop_constraint("ck_agents_handle_lowercase", "agents", type_="check")
    op.drop_column("agents", "handle")
