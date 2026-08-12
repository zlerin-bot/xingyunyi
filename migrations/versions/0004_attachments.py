"""Add private attachment metadata.

Revision ID: 0004_attachments
Revises: 0003_persistent_inbox
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_attachments"
down_revision: str | None = "0003_persistent_inbox"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("uploader_agent_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.String(length=64), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("storage_key", sa.String(length=64), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("state IN ('pending', 'attached')", name="ck_attachments_state"),
        sa.CheckConstraint("size >= 0", name="ck_attachments_nonnegative_size"),
        sa.CheckConstraint(
            "(state = 'pending' AND message_id IS NULL) OR "
            "(state = 'attached' AND message_id IS NOT NULL)",
            name="ck_attachments_state_message",
        ),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["uploader_agent_id"], ["agents.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_attachments_message_id", "attachments", ["message_id"], unique=False)
    op.create_index(
        "ix_attachments_uploader_agent_id",
        "attachments",
        ["uploader_agent_id"],
        unique=False,
    )
    op.create_index(
        "ix_attachments_uploader_state",
        "attachments",
        ["uploader_agent_id", "state"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("attachments")
