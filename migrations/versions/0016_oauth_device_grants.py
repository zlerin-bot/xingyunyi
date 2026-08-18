"""Add OAuth device grants and scoped Connector tokens.

Revision ID: 0016_oauth_device_grants
Revises: 0015_connector_lifecycle
Create Date: 2026-08-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_oauth_device_grants"
down_revision: str | None = "0015_connector_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("agent_pairing_sessions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "credential_mode",
                sa.String(length=32),
                nullable=False,
                server_default="agent_api_key",
            )
        )
        batch_op.add_column(sa.Column("oauth_client_id", sa.String(length=255)))
        batch_op.add_column(sa.Column("oauth_scope", sa.String(length=1000)))
        batch_op.add_column(sa.Column("oauth_resource", sa.String(length=1000)))
        batch_op.create_check_constraint(
            "ck_agent_pairing_sessions_credential_mode",
            "credential_mode IN ('agent_api_key', 'oauth')",
        )

    op.create_table(
        "oauth_access_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("token_prefix", sa.String(length=20), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("human_user_id", sa.Uuid(), nullable=False),
        sa.Column("connector_instance_id", sa.Uuid(), nullable=False),
        sa.Column("pairing_session_id", sa.Uuid()),
        sa.Column("refresh_family_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("scope", sa.String(length=1000), nullable=False),
        sa.Column("resource", sa.String(length=1000), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["human_user_id"], ["human_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["connector_instance_id"], ["connector_instances.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["pairing_session_id"], ["agent_pairing_sessions.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_digest"),
    )
    for column in (
        "token_prefix",
        "agent_id",
        "human_user_id",
        "connector_instance_id",
        "pairing_session_id",
        "refresh_family_id",
        "client_id",
        "expires_at",
    ):
        op.create_index(f"ix_oauth_access_tokens_{column}", "oauth_access_tokens", [column])

    op.create_table(
        "oauth_refresh_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("token_prefix", sa.String(length=20), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("human_user_id", sa.Uuid(), nullable=False),
        sa.Column("connector_instance_id", sa.Uuid(), nullable=False),
        sa.Column("pairing_session_id", sa.Uuid()),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("scope", sa.String(length=1000), nullable=False),
        sa.Column("resource", sa.String(length=1000), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revocation_reason", sa.String(length=32)),
        sa.CheckConstraint(
            "revocation_reason IN ('rotated', 'replayed', 'connector_replaced', "
            "'connector_revoked') OR revocation_reason IS NULL",
            name="ck_oauth_refresh_tokens_revocation_reason",
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["human_user_id"], ["human_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["connector_instance_id"], ["connector_instances.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["pairing_session_id"], ["agent_pairing_sessions.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_digest"),
    )
    for column in (
        "token_prefix",
        "family_id",
        "agent_id",
        "human_user_id",
        "connector_instance_id",
        "pairing_session_id",
        "client_id",
        "expires_at",
    ):
        op.create_index(f"ix_oauth_refresh_tokens_{column}", "oauth_refresh_tokens", [column])


def downgrade() -> None:
    op.drop_table("oauth_refresh_tokens")
    op.drop_table("oauth_access_tokens")
    with op.batch_alter_table("agent_pairing_sessions") as batch_op:
        batch_op.drop_constraint("ck_agent_pairing_sessions_credential_mode", type_="check")
        batch_op.drop_column("oauth_resource")
        batch_op.drop_column("oauth_scope")
        batch_op.drop_column("oauth_client_id")
        batch_op.drop_column("credential_mode")
