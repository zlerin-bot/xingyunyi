from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException, Request, status
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from agentpost.config import Settings
from agentpost.security.models import RateLimitBucket


@dataclass(frozen=True)
class RateLimitExceededError(Exception):
    retry_after: int


def _subject_digest(settings: Settings, *, scope: str, subject: str) -> str:
    return hmac.new(
        settings.rate_limit_secret.get_secret_value().encode("utf-8"),
        f"{scope}\0{subject}".encode(),
        hashlib.sha256,
    ).hexdigest()


def enforce_rate_limit(
    session: Session,
    settings: Settings,
    *,
    scope: str,
    subject: str,
    limit: int,
    window_seconds: int,
    now: datetime | None = None,
) -> None:
    if not settings.rate_limit_enabled:
        return
    if not scope or len(scope) > 80 or not subject or limit < 1 or window_seconds < 1:
        raise ValueError("invalid rate limit policy")
    current = (now or datetime.now(UTC)).astimezone(UTC)
    window_epoch = int(current.timestamp()) // window_seconds * window_seconds
    window_started_at = datetime.fromtimestamp(window_epoch, tz=UTC)
    expires_at = window_started_at + timedelta(seconds=window_seconds)
    values = {
        "id": uuid4(),
        "scope": scope,
        "subject_digest": _subject_digest(settings, scope=scope, subject=subject),
        "window_started_at": window_started_at,
        "request_count": 1,
        "expires_at": expires_at,
        "updated_at": current,
    }
    table = RateLimitBucket.__table__
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        statement = postgresql_insert(table).values(**values)
    elif dialect == "sqlite":
        statement = sqlite_insert(table).values(**values)
    else:
        raise RuntimeError("rate limiting requires PostgreSQL or SQLite")
    statement = statement.on_conflict_do_update(
        index_elements=["scope", "subject_digest", "window_started_at"],
        set_={
            "request_count": table.c.request_count + 1,
            "expires_at": expires_at,
            "updated_at": current,
        },
    ).returning(table.c.request_count)
    request_count = int(session.execute(statement).scalar_one())
    session.commit()
    if request_count > limit:
        retry_after = max(1, int((expires_at - current).total_seconds()) + 1)
        raise RateLimitExceededError(retry_after=retry_after)


def client_rate_limit_subject(request: Request) -> str:
    client = request.client
    return f"ip:{client.host if client is not None else 'unknown'}"


def enforce_http_rate_limit(
    request: Request,
    session: Session,
    settings: Settings,
    *,
    scope: str,
    subject: str,
    limit: int,
    window_seconds: int,
) -> None:
    try:
        enforce_rate_limit(
            session,
            settings,
            scope=scope,
            subject=subject,
            limit=limit,
            window_seconds=window_seconds,
        )
    except RateLimitExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "rate_limited", "message": "Try again later"},
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
