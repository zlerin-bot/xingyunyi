from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from agentpost.api.dependencies import SessionDep, SettingsDep
from agentpost.config import Settings
from agentpost.control.api_keys import digest_human_key
from agentpost.control.auth import CurrentHumanDep
from agentpost.control.models import (
    HumanActionAudit,
    HumanActionConfirmation,
    HumanSession,
    HumanUser,
)
from agentpost.control.sessions import verify_human_csrf_token
from agentpost.identity.models import utc_now

HUMAN_CSRF_HEADER = "X-CSRF-Token"
HUMAN_CONFIRMATION_HEADER = "X-Human-Confirmation"
HUMAN_CONFIRMATION_MARKER = "hcf_"
HUMAN_CONFIRMATION_RANDOM_BYTES = 32


class HumanConfirmationInvalidError(Exception):
    pass


@dataclass(frozen=True)
class CreatedHumanConfirmation:
    raw_token: str
    expires_at: datetime


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _request_session_id(request: Request) -> UUID | None:
    raw_session_id = getattr(request.state, "human_session_id", None)
    return UUID(raw_session_id) if raw_session_id else None


def add_human_action_audit(
    session: Session,
    *,
    human_user_id: UUID,
    human_session_id: UUID | None,
    action: str,
    target_type: str,
    target_id: str,
    outcome: str,
    request_id: str,
    reason_code: str | None = None,
    audit_metadata: dict[str, object] | None = None,
) -> HumanActionAudit:
    audit = HumanActionAudit(
        human_user_id=human_user_id,
        human_session_id=human_session_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        outcome=outcome,
        reason_code=reason_code,
        request_id=request_id,
        audit_metadata=audit_metadata or {},
        created_at=utc_now(),
    )
    session.add(audit)
    return audit


def _csrf_denied() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "invalid_csrf_token",
            "message": "A current same-origin CSRF token is required",
        },
    )


def require_human_csrf(
    request: Request,
    current_human: CurrentHumanDep,
    session: SessionDep,
    settings: SettingsDep,
    csrf_token: Annotated[str | None, Header(alias=HUMAN_CSRF_HEADER)] = None,
) -> None:
    if getattr(request.state, "human_authentication", None) != "browser_session":
        return
    human_session_id = _request_session_id(request)
    browser_session = session.get(HumanSession, human_session_id)
    if (
        browser_session is None
        or csrf_token is None
        or not verify_human_csrf_token(
            settings,
            browser_session=browser_session,
            raw_csrf_token=csrf_token,
        )
    ):
        add_human_action_audit(
            session,
            human_user_id=current_human.id,
            human_session_id=human_session_id,
            action="control.csrf_validation",
            target_type="http_route",
            target_id=request.url.path,
            outcome="denied",
            reason_code="invalid_csrf_token",
            request_id=request.state.request_id,
        )
        session.commit()
        raise _csrf_denied()


HumanCsrfDep = Annotated[None, Depends(require_human_csrf)]


def generate_human_confirmation_token() -> str:
    return f"{HUMAN_CONFIRMATION_MARKER}{secrets.token_urlsafe(HUMAN_CONFIRMATION_RANDOM_BYTES)}"


def create_human_confirmation(
    session: Session,
    settings: Settings,
    *,
    user: HumanUser,
    human_session_id: UUID | None,
    intent: str,
    target_type: str,
    target_id: str,
    request_id: str,
) -> CreatedHumanConfirmation:
    now = utc_now()
    expires_at = now + timedelta(seconds=settings.human_confirmation_ttl_seconds)
    raw_token = generate_human_confirmation_token()
    confirmation = HumanActionConfirmation(
        human_user_id=user.id,
        human_session_id=human_session_id,
        intent=intent,
        target_type=target_type,
        target_id=target_id,
        token_digest=digest_human_key(raw_token, settings.human_api_key_pepper),
        expires_at=expires_at,
        created_at=now,
    )
    session.add(confirmation)
    session.flush()
    add_human_action_audit(
        session,
        human_user_id=user.id,
        human_session_id=human_session_id,
        action="control.action_confirmation_created",
        target_type=target_type,
        target_id=target_id,
        outcome="success",
        request_id=request_id,
        audit_metadata={"intent": intent, "expires_at": expires_at.isoformat()},
    )
    session.commit()
    return CreatedHumanConfirmation(raw_token=raw_token, expires_at=expires_at)


def consume_human_confirmation(
    session: Session,
    settings: Settings,
    *,
    user: HumanUser,
    human_session_id: UUID | None,
    intent: str,
    target_type: str,
    target_id: str,
    raw_token: str,
) -> HumanActionConfirmation:
    if not raw_token.startswith(HUMAN_CONFIRMATION_MARKER) or not 20 <= len(raw_token) <= 256:
        raise HumanConfirmationInvalidError
    digest = digest_human_key(raw_token, settings.human_api_key_pepper)
    confirmation = session.scalar(
        select(HumanActionConfirmation)
        .where(HumanActionConfirmation.token_digest == digest)
        .with_for_update()
    )
    if (
        confirmation is None
        or confirmation.human_user_id != user.id
        or confirmation.human_session_id != human_session_id
        or confirmation.intent != intent
        or confirmation.target_type != target_type
        or confirmation.target_id != target_id
        or confirmation.consumed_at is not None
        or _as_utc(confirmation.expires_at) <= datetime.now(UTC)
    ):
        raise HumanConfirmationInvalidError
    confirmation.consumed_at = utc_now()
    return confirmation
