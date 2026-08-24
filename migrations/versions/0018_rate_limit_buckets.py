"""Add durable application rate limit buckets.

Revision ID: 0018_rate_limit_buckets
Revises: 0017_enterprise_oidc
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_rate_limit_buckets"
down_revision: str | None = "0017_enterprise_oidc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_buckets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(length=80), nullable=False),
        sa.Column("subject_digest", sa.String(length=64), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "request_count > 0",
            name="ck_rate_limit_bucket_positive_count",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "scope",
            "subject_digest",
            "window_started_at",
            name="uq_rate_limit_bucket_scope_subject_window",
        ),
    )
    op.create_index(
        "ix_rate_limit_buckets_window_started_at",
        "rate_limit_buckets",
        ["window_started_at"],
    )
    op.create_index(
        "ix_rate_limit_buckets_expires_at",
        "rate_limit_buckets",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_table("rate_limit_buckets")
