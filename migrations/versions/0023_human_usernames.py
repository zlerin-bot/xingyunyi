"""Add unique Human usernames for natural recipient resolution.

Revision ID: 0023_human_usernames
Revises: 0022_oauth_authorization_code
Create Date: 2026-08-27
"""

from __future__ import annotations

import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023_human_usernames"
down_revision: str | None = "0022_oauth_authorization_code"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_USERNAME_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,30}[a-z0-9])?$")


def _base_username(*, user_id: object, email: str, display_name: str) -> str:
    display_candidate = display_name.strip().lower()
    if _USERNAME_PATTERN.fullmatch(display_candidate) and "--" not in display_candidate:
        return display_candidate
    local_part = email.partition("@")[0].lower()
    email_candidate = re.sub(r"[^a-z0-9]+", "-", local_part).strip("-")
    if _USERNAME_PATTERN.fullmatch(email_candidate) and "--" not in email_candidate:
        return email_candidate
    identifier = re.sub(r"[^a-f0-9]", "", str(user_id).lower())[:12]
    return f"user-{identifier or 'legacy'}"


def upgrade() -> None:
    op.add_column("human_users", sa.Column("username", sa.String(length=32), nullable=True))
    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT id, email, display_name FROM human_users ORDER BY created_at, id")
    ).mappings()
    used: set[str] = set()
    for row in rows:
        base = _base_username(
            user_id=row["id"],
            email=row["email"],
            display_name=row["display_name"],
        )
        candidate = base
        suffix = 2
        while candidate in used:
            suffix_text = f"-{suffix}"
            candidate = f"{base[: 32 - len(suffix_text)].rstrip('-')}{suffix_text}"
            suffix += 1
        used.add(candidate)
        connection.execute(
            sa.text("UPDATE human_users SET username = :username WHERE id = :user_id"),
            {"username": candidate, "user_id": row["id"]},
        )
    op.alter_column("human_users", "username", existing_type=sa.String(length=32), nullable=False)
    op.create_check_constraint(
        "ck_human_users_username_lowercase",
        "human_users",
        "username = lower(username)",
    )
    op.create_index("ix_human_users_username", "human_users", ["username"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_human_users_username", table_name="human_users")
    op.drop_constraint("ck_human_users_username_lowercase", "human_users", type_="check")
    op.drop_column("human_users", "username")
