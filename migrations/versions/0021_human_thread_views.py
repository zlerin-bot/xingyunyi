"""Track Human viewing independently from Agent delivery and work state.

Revision ID: 0021_human_thread_views
Revises: 0020_pairing_agent_intent
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021_human_thread_views"
down_revision: str | None = "0020_pairing_agent_intent"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "human_thread_views",
        sa.Column("human_user_id", sa.Uuid(), nullable=False),
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("viewed_through_message_id", sa.String(length=64), nullable=False),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["human_user_id"],
            ["human_users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["viewed_through_message_id"],
            ["messages.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("human_user_id", "thread_id"),
    )
    op.create_index(
        "ix_human_thread_views_viewed_at",
        "human_thread_views",
        ["viewed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_human_thread_views_viewed_at", table_name="human_thread_views")
    op.drop_table("human_thread_views")
