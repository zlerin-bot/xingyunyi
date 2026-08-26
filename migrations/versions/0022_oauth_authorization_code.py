"""Add OAuth DCR and Authorization Code with PKCE transactions.

Revision ID: 0022_oauth_authorization_code
Revises: 0021_human_thread_views
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022_oauth_authorization_code"
down_revision: str | None = "0021_human_thread_views"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "oauth_dynamic_clients",
        sa.Column("client_id", sa.String(length=96), nullable=False),
        sa.Column("client_name", sa.String(length=200), nullable=False),
        sa.Column("redirect_uris", sa.JSON(), nullable=False),
        sa.Column("grant_types", sa.JSON(), nullable=False),
        sa.Column("response_types", sa.JSON(), nullable=False),
        sa.Column("token_endpoint_auth_method", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("client_id"),
    )
    op.create_index(
        "ix_oauth_dynamic_clients_expires_at",
        "oauth_dynamic_clients",
        ["expires_at"],
    )

    op.create_table(
        "oauth_authorization_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.String(length=80), nullable=False),
        sa.Column("pairing_session_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.String(length=96), nullable=False),
        sa.Column("redirect_uri", sa.String(length=1000), nullable=False),
        sa.Column("state", sa.String(length=2000)),
        sa.Column("scope", sa.String(length=1000), nullable=False),
        sa.Column("resource", sa.String(length=1000), nullable=False),
        sa.Column("new_agent_intent_id", sa.Uuid()),
        sa.Column("code_challenge", sa.String(length=128), nullable=False),
        sa.Column("code_challenge_method", sa.String(length=16), nullable=False),
        sa.Column("authorization_code_digest", sa.String(length=64)),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("code_expires_at", sa.DateTime(timezone=True)),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'denied', 'consumed', 'expired')",
            name="ck_oauth_authorization_requests_status",
        ),
        sa.ForeignKeyConstraint(
            ["pairing_session_id"],
            ["agent_pairing_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["oauth_dynamic_clients.client_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("authorization_code_digest"),
        sa.UniqueConstraint("new_agent_intent_id"),
        sa.UniqueConstraint("pairing_session_id"),
        sa.UniqueConstraint("request_id"),
    )
    for column in ("client_id", "status", "expires_at"):
        op.create_index(
            f"ix_oauth_authorization_requests_{column}",
            "oauth_authorization_requests",
            [column],
        )


def downgrade() -> None:
    op.drop_table("oauth_authorization_requests")
    op.drop_table("oauth_dynamic_clients")
