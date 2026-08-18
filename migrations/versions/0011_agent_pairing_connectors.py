"""Add Agent pairing sessions and single-current Connector bindings.

Revision ID: 0011_agent_pairing_connectors
Revises: 0010_approval_queue
Create Date: 2026-08-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_agent_pairing_connectors"
down_revision: str | None = "0010_approval_queue"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connector_instances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("connector_id", sa.String(length=64), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("human_user_id", sa.Uuid(), nullable=False),
        sa.Column("connector_type", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("device_name", sa.String(length=200), nullable=True),
        sa.Column("client_version", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.String(length=255), nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'replaced', 'revoked')",
            name="ck_connector_instances_status",
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["human_user_id"],
            ["human_users.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("connector_id"),
    )
    op.create_index(
        "ix_connector_instances_agent_id",
        "connector_instances",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        "ix_connector_instances_human_user_id",
        "connector_instances",
        ["human_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_connector_instances_connector_type",
        "connector_instances",
        ["connector_type"],
        unique=False,
    )
    op.create_index(
        "ix_connector_instances_status",
        "connector_instances",
        ["status"],
        unique=False,
    )

    op.create_table(
        "agent_connector_bindings",
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("connector_instance_id", sa.Uuid(), nullable=False),
        sa.Column("bound_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["connector_instance_id"],
            ["connector_instances.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("agent_id"),
        sa.UniqueConstraint("connector_instance_id"),
    )

    op.create_table(
        "agent_pairing_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pairing_id", sa.String(length=64), nullable=False),
        sa.Column("device_code_digest", sa.String(length=64), nullable=False),
        sa.Column("user_code_digest", sa.String(length=64), nullable=False),
        sa.Column("user_code_hint", sa.String(length=16), nullable=False),
        sa.Column("connector_type", sa.String(length=64), nullable=False),
        sa.Column("connector_display_name", sa.String(length=200), nullable=False),
        sa.Column("device_name", sa.String(length=200), nullable=True),
        sa.Column("client_version", sa.String(length=100), nullable=True),
        sa.Column("requested_capabilities", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("credential_delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by_human_id", sa.Uuid(), nullable=True),
        sa.Column("human_session_id", sa.Uuid(), nullable=True),
        sa.Column("agent_id", sa.Uuid(), nullable=True),
        sa.Column("connector_instance_id", sa.Uuid(), nullable=True),
        sa.Column("decision_idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("decision_request_hash", sa.String(length=64), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'denied', 'expired', 'consumed')",
            name="ck_agent_pairing_sessions_status",
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["connector_instance_id"],
            ["connector_instances.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_human_id"],
            ["human_users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["human_session_id"],
            ["human_sessions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pairing_id"),
        sa.UniqueConstraint("device_code_digest"),
        sa.UniqueConstraint("user_code_digest"),
        sa.UniqueConstraint("connector_instance_id"),
        sa.UniqueConstraint(
            "decided_by_human_id",
            "decision_idempotency_key",
            name="uq_pairing_sessions_human_idempotency",
        ),
    )
    op.create_index(
        "ix_agent_pairing_sessions_connector_type",
        "agent_pairing_sessions",
        ["connector_type"],
        unique=False,
    )
    op.create_index(
        "ix_agent_pairing_sessions_status",
        "agent_pairing_sessions",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_agent_pairing_sessions_expires_at",
        "agent_pairing_sessions",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_agent_pairing_sessions_created_at",
        "agent_pairing_sessions",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_agent_pairing_sessions_decided_by_human_id",
        "agent_pairing_sessions",
        ["decided_by_human_id"],
        unique=False,
    )
    op.create_index(
        "ix_agent_pairing_sessions_human_session_id",
        "agent_pairing_sessions",
        ["human_session_id"],
        unique=False,
    )
    op.create_index(
        "ix_agent_pairing_sessions_agent_id",
        "agent_pairing_sessions",
        ["agent_id"],
        unique=False,
    )

    with op.batch_alter_table("agent_api_keys") as batch_op:
        batch_op.add_column(sa.Column("connector_instance_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_agent_api_keys_connector_instance_id",
            "connector_instances",
            ["connector_instance_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_agent_api_keys_connector_instance_id",
            ["connector_instance_id"],
            unique=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("agent_api_keys") as batch_op:
        batch_op.drop_index("ix_agent_api_keys_connector_instance_id")
        batch_op.drop_constraint(
            "fk_agent_api_keys_connector_instance_id",
            type_="foreignkey",
        )
        batch_op.drop_column("connector_instance_id")

    op.drop_table("agent_pairing_sessions")
    op.drop_table("agent_connector_bindings")
    op.drop_table("connector_instances")
