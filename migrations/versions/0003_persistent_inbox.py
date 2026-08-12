"""Add durable messages, deliveries, idempotency, and audit logs.

Revision ID: 0003_persistent_inbox
Revises: 0002_agent_identity
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_persistent_inbox"
down_revision: str | None = "0002_agent_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "messages",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("sender_agent_id", sa.Uuid(), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("content_format", sa.String(length=32), nullable=False),
        sa.Column("content_body", sa.JSON(), nullable=False),
        sa.Column("message_type", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("reply_to_message_id", sa.String(length=64), nullable=True),
        sa.Column("requires_ack", sa.Boolean(), nullable=False),
        sa.Column("task_payload", sa.JSON(), nullable=True),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("message_metadata", sa.JSON(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "message_type IN ('message', 'task', 'result', 'request', 'response', "
            "'notification', 'event', 'error', 'system')",
            name="ck_messages_type",
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'urgent')",
            name="ck_messages_priority",
        ),
        sa.ForeignKeyConstraint(["reply_to_message_id"], ["messages.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sender_agent_id"], ["agents.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_created_at", "messages", ["created_at"], unique=False)
    op.create_index(
        "ix_messages_reply_to_message_id",
        "messages",
        ["reply_to_message_id"],
        unique=False,
    )
    op.create_index("ix_messages_sender_agent_id", "messages", ["sender_agent_id"], unique=False)
    op.create_index(
        "ix_messages_thread_created",
        "messages",
        ["thread_id", "created_at", "id"],
        unique=False,
    )
    op.create_index("ix_messages_thread_id", "messages", ["thread_id"], unique=False)

    op.create_table(
        "deliveries",
        sa.Column(
            "inbox_seq",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.String(length=64), nullable=False),
        sa.Column("recipient_agent_id", sa.Uuid(), nullable=False),
        sa.Column("delivery_status", sa.String(length=32), nullable=False),
        sa.Column("delivery_attempts", sa.Integer(), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "delivery_status IN ('accepted', 'delivered', 'read', 'acked', "
            "'failed', 'expired', 'rejected')",
            name="ck_deliveries_status",
        ),
        sa.CheckConstraint(
            "acked_at IS NULL OR read_at IS NOT NULL",
            name="ck_deliveries_ack_implies_read",
        ),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipient_agent_id"], ["agents.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("inbox_seq"),
        sa.UniqueConstraint("id", name="uq_deliveries_id"),
        sa.UniqueConstraint(
            "message_id",
            "recipient_agent_id",
            name="uq_deliveries_message_recipient",
        ),
    )
    op.create_index("ix_deliveries_message_id", "deliveries", ["message_id"], unique=False)
    op.create_index(
        "ix_deliveries_recipient_agent_id",
        "deliveries",
        ["recipient_agent_id"],
        unique=False,
    )
    op.create_index(
        "ix_deliveries_recipient_seq",
        "deliveries",
        ["recipient_agent_id", "inbox_seq"],
        unique=False,
    )
    op.create_index(
        "ix_deliveries_recipient_status_seq",
        "deliveries",
        ["recipient_agent_id", "delivery_status", "inbox_seq"],
        unique=False,
    )

    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sender_agent_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("operation", sa.String(length=32), nullable=False),
        sa.Column("message_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id"),
        sa.UniqueConstraint(
            "sender_agent_id",
            "idempotency_key",
            name="uq_idempotency_sender_key",
        ),
    )
    op.create_index(
        "ix_idempotency_records_sender_agent_id",
        "idempotency_records",
        ["sender_agent_id"],
        unique=False,
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_agent_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=False),
        sa.Column("target_id", sa.String(length=255), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("reason_code", sa.String(length=100), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("audit_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_agent_id"], ["agents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_actor_agent_id", "audit_logs", ["actor_agent_id"], unique=False)
    op.create_index(
        "ix_audit_logs_actor_created",
        "audit_logs",
        ["actor_agent_id", "created_at"],
        unique=False,
    )
    op.create_index("ix_audit_logs_request_id", "audit_logs", ["request_id"], unique=False)


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("idempotency_records")
    op.drop_table("deliveries")
    op.drop_table("messages")
