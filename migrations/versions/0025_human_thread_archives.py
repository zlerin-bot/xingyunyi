"""Keep per-Human reversible Orbit thread archives.

Revision ID: 0025_human_thread_archives
Revises: 0024_human_default_agent
Create Date: 2026-08-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025_human_thread_archives"
down_revision: str | None = "0024_human_default_agent"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "human_thread_archives",
        sa.Column("human_user_id", sa.Uuid(), nullable=False),
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["human_user_id"],
            ["human_users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("human_user_id", "thread_id"),
    )
    op.create_index(
        "ix_human_thread_archives_archived_at",
        "human_thread_archives",
        ["archived_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_human_thread_archives_archived_at",
        table_name="human_thread_archives",
    )
    op.drop_table("human_thread_archives")
