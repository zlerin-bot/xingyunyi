from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from agentpost.api.dependencies import SessionDep, SettingsDep
from agentpost.control.api_keys import HUMAN_KEY_MARKER, digest_human_key
from agentpost.control.models import HumanAccessKey, HumanUser

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


def get_current_human(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_human_bearer)],
) -> HumanUser:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise _human_authentication_error()

    raw_key = credentials.credentials
    if not raw_key.startswith(HUMAN_KEY_MARKER) or not 20 <= len(raw_key) <= 256:
        raise _human_authentication_error()

    digest = digest_human_key(raw_key, settings.human_api_key_pepper)
    credential = session.scalar(select(HumanAccessKey).where(HumanAccessKey.key_digest == digest))
    if (
        credential is None
        or credential.revoked_at is not None
        or credential.user.status != "active"
    ):
        raise _human_authentication_error()

    now = datetime.now(UTC)
    credential.last_used_at = now
    credential.user.last_seen_at = now
    session.commit()
    request.state.human_user_id = str(credential.user.id)
    return credential.user


CurrentHumanDep = Annotated[HumanUser, Depends(get_current_human)]
