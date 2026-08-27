from __future__ import annotations

import re
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

HUMAN_USERNAME_PATTERN = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]{1,30}[a-z0-9])?$",
    flags=re.ASCII,
)


class HumanUsernameAlreadyRegisteredError(Exception):
    pass


def canonicalize_human_username(value: str) -> str:
    username = value.strip().lower()
    if not HUMAN_USERNAME_PATTERN.fullmatch(username) or "--" in username:
        raise ValueError("username must use 3-32 lowercase letters, digits, or single hyphens")
    return username


def generated_human_username() -> str:
    return f"user-{uuid4().hex[:12]}"


def available_human_username(
    session: Session,
    *,
    requested: str | None,
    email: str,
) -> str:
    from agentpost.control.models import HumanUser

    if requested is not None:
        candidate = canonicalize_human_username(requested)
        if session.scalar(select(HumanUser.id).where(HumanUser.username == candidate)) is not None:
            raise HumanUsernameAlreadyRegisteredError(candidate)
        return candidate

    local_part = email.partition("@")[0].lower()
    base = re.sub(r"[^a-z0-9]+", "-", local_part).strip("-")
    if len(base) < 3 or len(base) > 32 or not HUMAN_USERNAME_PATTERN.fullmatch(base):
        base = generated_human_username()
    candidate = base
    suffix = 2
    while session.scalar(select(HumanUser.id).where(HumanUser.username == candidate)) is not None:
        suffix_text = f"-{suffix}"
        candidate = f"{base[: 32 - len(suffix_text)].rstrip('-')}{suffix_text}"
        suffix += 1
    return candidate
