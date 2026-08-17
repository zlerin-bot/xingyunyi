"""Add short-lived Human browser sessions.

Revision ID: 0007_human_sessions
Revises: 0006_human_control_plane
Create Date: 2026-08-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_human_sessions"
down_revision: str | None = "0006_human_control_plane"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "human_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("human_user_id", sa.Uuid(), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["human_user_id"], ["human_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_digest"),
    )
    op.create_index(
        "ix_human_sessions_human_user_id",
        "human_sessions",
        ["human_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_human_sessions_expires_at",
        "human_sessions",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("human_sessions")
