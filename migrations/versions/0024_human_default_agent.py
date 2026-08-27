"""Add each Human's explicit default Agent.

Revision ID: 0024_human_default_agent
Revises: 0023_human_usernames
Create Date: 2026-08-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024_human_default_agent"
down_revision: str | None = "0023_human_usernames"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "human_users",
        sa.Column("default_agent_id", sa.Uuid(), nullable=True),
    )
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            """
            SELECT ao.human_user_id, ao.agent_id
            FROM agent_ownerships AS ao
            JOIN agents AS a ON a.id = ao.agent_id
            WHERE a.status = 'active'
            ORDER BY ao.human_user_id, ao.assigned_at, a.address, ao.agent_id
            """
        )
    ).mappings()
    assigned_humans: set[object] = set()
    for row in rows:
        human_user_id = row["human_user_id"]
        if human_user_id in assigned_humans:
            continue
        assigned_humans.add(human_user_id)
        connection.execute(
            sa.text(
                "UPDATE human_users SET default_agent_id = :agent_id WHERE id = :human_user_id"
            ),
            {"agent_id": row["agent_id"], "human_user_id": human_user_id},
        )
    op.create_index(
        "ix_human_users_default_agent_id",
        "human_users",
        ["default_agent_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_human_users_default_agent_id_agents",
        "human_users",
        "agents",
        ["default_agent_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_human_users_default_agent_id_agents",
        "human_users",
        type_="foreignkey",
    )
    op.drop_index("ix_human_users_default_agent_id", table_name="human_users")
    op.drop_column("human_users", "default_agent_id")
