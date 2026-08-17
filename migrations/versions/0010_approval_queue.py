"""Add durable Human approval requests and decisions.

Revision ID: 0010_approval_queue
Revises: 0009_human_action_security
Create Date: 2026-08-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_approval_queue"
down_revision: str | None = "0009_human_action_security"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("approval_id", sa.String(length=64), nullable=False),
        sa.Column("requested_by_agent_id", sa.Uuid(), nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.String(length=300), nullable=False),
        sa.Column("justification", sa.String(length=2000), nullable=True),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "risk_level IN ('low', 'medium', 'high', 'critical')",
            name="ck_approval_requests_risk_level",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled', 'expired')",
            name="ck_approval_requests_status",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_agent_id"],
            ["agents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("approval_id"),
        sa.UniqueConstraint(
            "requested_by_agent_id",
            "idempotency_key",
            name="uq_approval_requests_agent_idempotency",
        ),
    )
    op.create_index(
        "ix_approval_requests_requested_by_agent_id",
        "approval_requests",
        ["requested_by_agent_id"],
        unique=False,
    )
    op.create_index(
        "ix_approval_requests_action_type",
        "approval_requests",
        ["action_type"],
        unique=False,
    )
    op.create_index(
        "ix_approval_requests_risk_level",
        "approval_requests",
        ["risk_level"],
        unique=False,
    )
    op.create_index(
        "ix_approval_requests_status",
        "approval_requests",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_approval_requests_expires_at",
        "approval_requests",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_approval_requests_created_at",
        "approval_requests",
        ["created_at"],
        unique=False,
    )
    op.create_table(
        "approval_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("approval_request_id", sa.Uuid(), nullable=False),
        sa.Column("human_user_id", sa.Uuid(), nullable=False),
        sa.Column("human_session_id", sa.Uuid(), nullable=True),
        sa.Column("confirmation_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("note", sa.String(length=1000), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision IN ('approved', 'rejected')",
            name="ck_approval_decisions_decision",
        ),
        sa.ForeignKeyConstraint(
            ["approval_request_id"],
            ["approval_requests.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["confirmation_id"],
            ["human_action_confirmations.id"],
            ondelete="RESTRICT",
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
        sa.UniqueConstraint("approval_request_id"),
        sa.UniqueConstraint("confirmation_id"),
        sa.UniqueConstraint(
            "human_user_id",
            "idempotency_key",
            name="uq_approval_decisions_human_idempotency",
        ),
    )
    op.create_index(
        "ix_approval_decisions_approval_request_id",
        "approval_decisions",
        ["approval_request_id"],
        unique=True,
    )
    op.create_index(
        "ix_approval_decisions_human_user_id",
        "approval_decisions",
        ["human_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_approval_decisions_human_session_id",
        "approval_decisions",
        ["human_session_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("approval_decisions")
    op.drop_table("approval_requests")
