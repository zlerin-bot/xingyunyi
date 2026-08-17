from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from agentpost.config import Settings
from agentpost.control.api_keys import digest_human_key
from agentpost.control.models import HumanSession, HumanUser
from agentpost.identity.models import utc_now
from agentpost.messaging.models import AuditLog

HUMAN_SESSION_COOKIE = "xinggui_session"
HUMAN_SESSION_MARKER = "hss_"
HUMAN_SESSION_RANDOM_BYTES = 32
HUMAN_CSRF_MARKER = "csrf_"
HUMAN_CSRF_RANDOM_BYTES = 32


@dataclass(frozen=True)
class CreatedHumanSession:
    raw_token: str
    raw_csrf_token: str
    expires_at: datetime


def generate_human_session_token() -> str:
    return f"{HUMAN_SESSION_MARKER}{secrets.token_urlsafe(HUMAN_SESSION_RANDOM_BYTES)}"


def generate_human_csrf_token() -> str:
    return f"{HUMAN_CSRF_MARKER}{secrets.token_urlsafe(HUMAN_CSRF_RANDOM_BYTES)}"


def digest_human_session_token(raw_token: str, settings: Settings) -> str:
    return digest_human_key(raw_token, settings.human_api_key_pepper)


def digest_human_csrf_token(raw_token: str, settings: Settings) -> str:
    return digest_human_key(raw_token, settings.human_api_key_pepper)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def create_human_session(
    session: Session,
    settings: Settings,
    *,
    user: HumanUser,
    request_id: str,
) -> CreatedHumanSession:
    now = utc_now()
    expires_at = now + timedelta(seconds=settings.human_session_ttl_seconds)
    raw_token = generate_human_session_token()
    raw_csrf_token = generate_human_csrf_token()
    browser_session = HumanSession(
        human_user_id=user.id,
        token_digest=digest_human_session_token(raw_token, settings),
        csrf_token_digest=digest_human_csrf_token(raw_csrf_token, settings),
        created_at=now,
        expires_at=expires_at,
        last_seen_at=now,
    )
    session.add(browser_session)
    session.flush()
    session.add(
        AuditLog(
            actor_agent_id=None,
            action="control.session_created",
            target_type="human_session",
            target_id=str(browser_session.id),
            outcome="success",
            request_id=request_id,
            audit_metadata={
                "human_user_id": str(user.id),
                "expires_at": expires_at.isoformat(),
            },
            created_at=now,
        )
    )
    session.commit()
    return CreatedHumanSession(
        raw_token=raw_token,
        raw_csrf_token=raw_csrf_token,
        expires_at=expires_at,
    )


def rotate_human_csrf_token(
    session: Session,
    settings: Settings,
    *,
    browser_session: HumanSession,
) -> str:
    raw_csrf_token = generate_human_csrf_token()
    browser_session.csrf_token_digest = digest_human_csrf_token(raw_csrf_token, settings)
    session.commit()
    return raw_csrf_token


def verify_human_csrf_token(
    settings: Settings,
    *,
    browser_session: HumanSession,
    raw_csrf_token: str,
) -> bool:
    stored = browser_session.csrf_token_digest
    if (
        stored is None
        or not raw_csrf_token.startswith(HUMAN_CSRF_MARKER)
        or not 20 <= len(raw_csrf_token) <= 256
    ):
        return False
    candidate = digest_human_csrf_token(raw_csrf_token, settings)
    return secrets.compare_digest(stored, candidate)


def resolve_human_session(
    session: Session,
    settings: Settings,
    *,
    raw_token: str,
) -> tuple[HumanUser, HumanSession] | None:
    if not raw_token.startswith(HUMAN_SESSION_MARKER) or not 20 <= len(raw_token) <= 256:
        return None
    token_digest = digest_human_session_token(raw_token, settings)
    browser_session = session.scalar(
        select(HumanSession).where(HumanSession.token_digest == token_digest)
    )
    if (
        browser_session is None
        or browser_session.revoked_at is not None
        or _as_utc(browser_session.expires_at) <= datetime.now(UTC)
        or browser_session.user.status != "active"
    ):
        return None
    return browser_session.user, browser_session


def revoke_human_session(
    session: Session,
    settings: Settings,
    *,
    raw_token: str,
    request_id: str,
) -> bool:
    resolved = resolve_human_session(session, settings, raw_token=raw_token)
    if resolved is None:
        return False
    user, browser_session = resolved
    now = utc_now()
    browser_session.revoked_at = now
    session.add(
        AuditLog(
            actor_agent_id=None,
            action="control.session_revoked",
            target_type="human_session",
            target_id=str(browser_session.id),
            outcome="success",
            request_id=request_id,
            audit_metadata={"human_user_id": str(user.id)},
            created_at=now,
        )
    )
    session.commit()
    return True
