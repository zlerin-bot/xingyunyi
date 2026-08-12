"""Add inbound access policies and allow/block rules.

Revision ID: 0005_access_control
Revises: 0004_attachments
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_access_control"
down_revision: str | None = "0004_attachments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("agents") as batch_op:
        batch_op.add_column(
            sa.Column(
                "inbound_policy",
                sa.String(length=32),
                server_default="public",
                nullable=False,
            ),
        )
        batch_op.create_check_constraint(
            "ck_agents_inbound_policy",
            "inbound_policy IN ('public', 'allowlist', 'contacts_only', 'private')",
        )
    op.create_table(
        "access_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_agent_id", sa.Uuid(), nullable=False),
        sa.Column("effect", sa.String(length=16), nullable=False),
        sa.Column("subject_type", sa.String(length=16), nullable=False),
        sa.Column("subject", sa.String(length=320), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("effect IN ('allow', 'block')", name="ck_access_rules_effect"),
        sa.CheckConstraint(
            "subject_type IN ('agent', 'domain')",
            name="ck_access_rules_subject_type",
        ),
        sa.ForeignKeyConstraint(["owner_agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_agent_id",
            "effect",
            "subject_type",
            "subject",
            name="uq_access_rules_owner_effect_type_subject",
        ),
    )
    op.create_index(
        "ix_access_rules_owner_agent_id",
        "access_rules",
        ["owner_agent_id"],
        unique=False,
    )
    op.create_index(
        "ix_access_rules_owner_subject",
        "access_rules",
        ["owner_agent_id", "subject_type", "subject"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("access_rules")
    with op.batch_alter_table("agents") as batch_op:
        batch_op.drop_constraint("ck_agents_inbound_policy", type_="check")
        batch_op.drop_column("inbound_policy")
