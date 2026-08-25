"""Add an optional existing-Agent intent to short-lived pairing sessions.

Revision ID: 0020_pairing_agent_intent
Revises: 0019_agent_handles
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020_pairing_agent_intent"
down_revision: str | None = "0019_agent_handles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_pairing_sessions",
        sa.Column("requested_existing_agent_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "ix_agent_pairing_sessions_requested_existing_agent_id",
        "agent_pairing_sessions",
        ["requested_existing_agent_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_agent_pairing_sessions_requested_existing_agent_id",
        table_name="agent_pairing_sessions",
    )
    op.drop_column("agent_pairing_sessions", "requested_existing_agent_id")
