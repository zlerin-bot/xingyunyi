"""Add Human self-service email, password, MFA, and recovery state.

Revision ID: 0012_human_self_service_auth
Revises: 0011_agent_pairing_connectors
Create Date: 2026-08-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_human_self_service_auth"
down_revision: str | None = "0011_agent_pairing_connectors"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("human_users") as batch_op:
        batch_op.add_column(sa.Column("email_verified_at", sa.DateTime(timezone=True)))

    with op.batch_alter_table("human_access_keys") as batch_op:
        batch_op.add_column(
            sa.Column("label", sa.String(length=100), nullable=False, server_default="legacy")
        )

    with op.batch_alter_table("human_sessions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "auth_method",
                sa.String(length=32),
                nullable=False,
                server_default="access_key",
            )
        )
        batch_op.add_column(sa.Column("mfa_authenticated_at", sa.DateTime(timezone=True)))

    op.create_table(
        "human_password_credentials",
        sa.Column("human_user_id", sa.Uuid(), nullable=False),
        sa.Column("salt", sa.String(length=128), nullable=False),
        sa.Column("password_hash", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["human_user_id"], ["human_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("human_user_id"),
    )
    op.create_table(
        "human_email_challenges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("challenge_id", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("purpose", sa.String(length=16), nullable=False),
        sa.Column("code_digest", sa.String(length=64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "purpose IN ('register', 'recover')",
            name="ck_human_email_challenges_purpose",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("challenge_id"),
    )
    op.create_index(
        "ix_human_email_challenges_email",
        "human_email_challenges",
        ["email"],
    )
    op.create_index(
        "ix_human_email_challenges_expires_at",
        "human_email_challenges",
        ["expires_at"],
    )
    op.create_index(
        "ix_human_email_challenges_created_at",
        "human_email_challenges",
        ["created_at"],
    )
    op.create_table(
        "human_totp_credentials",
        sa.Column("human_user_id", sa.Uuid(), nullable=False),
        sa.Column("encrypted_secret", sa.String(length=512), nullable=False),
        sa.Column("pending", sa.Boolean(), nullable=False),
        sa.Column("recovery_code_digests", sa.String(length=2000), nullable=False),
        sa.Column("last_used_step", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("enabled_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["human_user_id"], ["human_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("human_user_id"),
    )


def downgrade() -> None:
    op.drop_table("human_totp_credentials")
    op.drop_table("human_email_challenges")
    op.drop_table("human_password_credentials")
    with op.batch_alter_table("human_sessions") as batch_op:
        batch_op.drop_column("mfa_authenticated_at")
        batch_op.drop_column("auth_method")
    with op.batch_alter_table("human_access_keys") as batch_op:
        batch_op.drop_column("label")
    with op.batch_alter_table("human_users") as batch_op:
        batch_op.drop_column("email_verified_at")
