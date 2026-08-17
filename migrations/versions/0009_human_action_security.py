"""Add Human CSRF, step-up confirmation, and action audit records.

Revision ID: 0009_human_action_security
Revises: 0008_organizations
Create Date: 2026-08-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_human_action_security"
down_revision: str | None = "0008_organizations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "human_sessions",
        sa.Column("csrf_token_digest", sa.String(length=64), nullable=True),
    )
    op.create_table(
        "human_action_confirmations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("human_user_id", sa.Uuid(), nullable=False),
        sa.Column("human_session_id", sa.Uuid(), nullable=True),
        sa.Column("intent", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=255), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["human_session_id"],
            ["human_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["human_user_id"],
            ["human_users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_digest"),
    )
    op.create_index(
        "ix_human_action_confirmations_human_user_id",
        "human_action_confirmations",
        ["human_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_human_action_confirmations_human_session_id",
        "human_action_confirmations",
        ["human_session_id"],
        unique=False,
    )
    op.create_index(
        "ix_human_action_confirmations_expires_at",
        "human_action_confirmations",
        ["expires_at"],
        unique=False,
    )
    op.create_table(
        "human_action_audits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("human_user_id", sa.Uuid(), nullable=False),
        sa.Column("human_session_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=255), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("audit_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('success', 'denied', 'failure')",
            name="ck_human_action_audits_outcome",
        ),
        sa.ForeignKeyConstraint(
            ["human_session_id"],
            ["human_sessions.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["human_user_id"],
            ["human_users.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_human_action_audits_human_user_id",
        "human_action_audits",
        ["human_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_human_action_audits_human_session_id",
        "human_action_audits",
        ["human_session_id"],
        unique=False,
    )
    op.create_index(
        "ix_human_action_audits_action",
        "human_action_audits",
        ["action"],
        unique=False,
    )
    op.create_index(
        "ix_human_action_audits_request_id",
        "human_action_audits",
        ["request_id"],
        unique=False,
    )
    op.create_index(
        "ix_human_action_audits_created_at",
        "human_action_audits",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("human_action_audits")
    op.drop_table("human_action_confirmations")
    with op.batch_alter_table("human_sessions") as batch_op:
        batch_op.drop_column("csrf_token_digest")
