"""Add persisted projects, memberships, and project activity.

Revision ID: 0027_projects
Revises: 0026_message_attachment_links
Create Date: 2026-09-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027_projects"
down_revision: str | None = "0026_message_attachment_links"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_human_user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_projects_status"),
        sa.ForeignKeyConstraint(["owner_human_user_id"], ["human_users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_owner_human_user_id", "projects", ["owner_human_user_id"])
    op.create_index("ix_projects_status", "projects", ["status"])

    op.create_table(
        "project_memberships",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("human_user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("invited_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('owner', 'member')", name="ck_project_memberships_role"),
        sa.CheckConstraint(
            "status IN ('invited', 'active', 'declined')",
            name="ck_project_memberships_status",
        ),
        sa.ForeignKeyConstraint(["human_user_id"], ["human_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["human_users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("project_id", "human_user_id"),
    )
    op.create_index(
        "ix_project_memberships_human_user_id",
        "project_memberships",
        ["human_user_id"],
    )

    op.create_table(
        "project_activities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("activity_type", sa.String(length=32), nullable=False),
        sa.Column("actor_human_user_id", sa.Uuid(), nullable=True),
        sa.Column("target_human_user_id", sa.Uuid(), nullable=True),
        sa.Column("activity_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "activity_type IN ('created', 'member_invited', 'member_joined', "
            "'member_declined', 'archived', 'restored')",
            name="ck_project_activities_type",
        ),
        sa.ForeignKeyConstraint(["actor_human_user_id"], ["human_users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_human_user_id"], ["human_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_activities_project_id", "project_activities", ["project_id"])
    op.create_index("ix_project_activities_created_at", "project_activities", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_project_activities_created_at", table_name="project_activities")
    op.drop_index("ix_project_activities_project_id", table_name="project_activities")
    op.drop_table("project_activities")
    op.drop_index("ix_project_memberships_human_user_id", table_name="project_memberships")
    op.drop_table("project_memberships")
    op.drop_index("ix_projects_status", table_name="projects")
    op.drop_index("ix_projects_owner_human_user_id", table_name="projects")
    op.drop_table("projects")
