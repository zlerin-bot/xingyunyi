"""Allow one attachment to appear on every delivery copy of an organization Event.

Revision ID: 0026_message_attachment_links
Revises: 0025_human_thread_archives
Create Date: 2026-08-30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026_message_attachment_links"
down_revision: str | None = "0025_human_thread_archives"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "message_attachments",
        sa.Column("message_id", sa.String(length=64), nullable=False),
        sa.Column("attachment_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["attachment_id"], ["attachments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("message_id", "attachment_id"),
    )
    op.create_index(
        "ix_message_attachments_attachment",
        "message_attachments",
        ["attachment_id"],
    )
    op.execute(
        sa.text(
            "INSERT INTO message_attachments (message_id, attachment_id) "
            "SELECT message_id, id FROM attachments "
            "WHERE state = 'attached' AND message_id IS NOT NULL"
        )
    )


def downgrade() -> None:
    op.drop_index(
        "ix_message_attachments_attachment",
        table_name="message_attachments",
    )
    op.drop_table("message_attachments")
