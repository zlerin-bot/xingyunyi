"""Add Connector heartbeat and credential lifecycle state.

Revision ID: 0015_connector_lifecycle
Revises: 0014_organization_domain_verification
Create Date: 2026-08-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_connector_lifecycle"
down_revision: str | None = "0014_organization_domain_verification"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("connector_instances") as batch_op:
        batch_op.add_column(
            sa.Column(
                "health_status",
                sa.String(length=16),
                nullable=False,
                server_default="unknown",
            )
        )
        batch_op.add_column(sa.Column("last_heartbeat_at", sa.DateTime(timezone=True)))
        batch_op.add_column(sa.Column("last_error_code", sa.String(length=100)))
        batch_op.add_column(sa.Column("last_error_at", sa.DateTime(timezone=True)))
        batch_op.add_column(sa.Column("credential_rotated_at", sa.DateTime(timezone=True)))
        batch_op.create_check_constraint(
            "ck_connector_instances_health_status",
            "health_status IN ('unknown', 'healthy', 'degraded', 'error')",
        )
        batch_op.create_index(
            "ix_connector_instances_health_status",
            ["health_status"],
        )
        batch_op.create_index(
            "ix_connector_instances_last_heartbeat_at",
            ["last_heartbeat_at"],
        )


def downgrade() -> None:
    with op.batch_alter_table("connector_instances") as batch_op:
        batch_op.drop_index("ix_connector_instances_last_heartbeat_at")
        batch_op.drop_index("ix_connector_instances_health_status")
        batch_op.drop_constraint(
            "ck_connector_instances_health_status",
            type_="check",
        )
        batch_op.drop_column("credential_rotated_at")
        batch_op.drop_column("last_error_at")
        batch_op.drop_column("last_error_code")
        batch_op.drop_column("last_heartbeat_at")
        batch_op.drop_column("health_status")
