from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from agentpost.api.dependencies import SessionDep, SettingsDep
from agentpost.control.api_keys import HUMAN_KEY_MARKER, digest_human_key
from agentpost.control.models import HumanAccessKey, HumanUser
from agentpost.control.sessions import HUMAN_SESSION_COOKIE, resolve_human_session

_human_bearer = HTTPBearer(auto_error=False)


def _human_authentication_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "code": "invalid_human_access_key",
            "message": "A valid Human access key is required",
        },
        headers={"WWW-Authenticate": "Bearer"},
    )


def _resolve_human_access_key(
    session: SessionDep,
    settings: SettingsDep,
    credentials: HTTPAuthorizationCredentials | None,
) -> tuple[HumanUser, HumanAccessKey] | None:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        return None

    raw_key = credentials.credentials
    if not raw_key.startswith(HUMAN_KEY_MARKER) or not 20 <= len(raw_key) <= 256:
        return None

    digest = digest_human_key(raw_key, settings.human_api_key_pepper)
    credential = session.scalar(select(HumanAccessKey).where(HumanAccessKey.key_digest == digest))
    if (
        credential is None
        or credential.revoked_at is not None
        or credential.user.status != "active"
    ):
        return None

    return credential.user, credential


def get_human_from_access_key(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_human_bearer)],
) -> HumanUser:
    resolved = _resolve_human_access_key(session, settings, credentials)
    if resolved is None:
        raise _human_authentication_error()
    user, credential = resolved

    now = datetime.now(UTC)
    credential.last_used_at = now
    user.last_seen_at = now
    session.commit()
    request.state.human_user_id = str(user.id)
    request.state.human_authentication = "access_key"
    return user


def get_optional_human_from_access_key(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_human_bearer)],
) -> HumanUser | None:
    resolved = _resolve_human_access_key(session, settings, credentials)
    if resolved is None:
        return None
    user, credential = resolved
    now = datetime.now(UTC)
    credential.last_used_at = now
    user.last_seen_at = now
    session.commit()
    request.state.human_reauthentication = "access_key"
    return user


def get_current_human(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_human_bearer)],
) -> HumanUser:
    raw_session = request.cookies.get(HUMAN_SESSION_COOKIE, "")
    resolved_session = resolve_human_session(session, settings, raw_token=raw_session)
    if resolved_session is not None:
        user, browser_session = resolved_session
        now = datetime.now(UTC)
        browser_session.last_seen_at = now
        user.last_seen_at = now
        session.commit()
        request.state.human_user_id = str(user.id)
        request.state.human_session_id = str(browser_session.id)
        request.state.human_authentication = "browser_session"
        return user

    resolved_key = _resolve_human_access_key(session, settings, credentials)
    if resolved_key is None:
        raise _human_authentication_error()
    user, credential = resolved_key
    now = datetime.now(UTC)
    credential.last_used_at = now
    user.last_seen_at = now
    session.commit()
    request.state.human_user_id = str(user.id)
    request.state.human_authentication = "access_key"
    return user


CurrentHumanDep = Annotated[HumanUser, Depends(get_current_human)]
HumanAccessKeyDep = Annotated[HumanUser, Depends(get_human_from_access_key)]
OptionalHumanAccessKeyDep = Annotated[
    HumanUser | None,
    Depends(get_optional_human_from_access_key),
]
