from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from agentpost.config import Settings
from agentpost.db import Database
from agentpost.identity.api_keys import API_KEY_MARKER, digest_api_key
from agentpost.identity.models import Agent, AgentApiKey


def get_database(request: Request) -> Database:
    return request.app.state.database


def get_runtime_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_session(database: Annotated[Database, Depends(get_database)]):
    yield from database.session()


DatabaseDep = Annotated[Database, Depends(get_database)]
SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_runtime_settings)]

_bearer_scheme = HTTPBearer(auto_error=False)


def _authentication_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "invalid_api_key", "message": "A valid Agent API key is required"},
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_agent(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> Agent:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _authentication_error()

    raw_api_key = credentials.credentials
    if (
        not raw_api_key.startswith(API_KEY_MARKER)
        or len(raw_api_key) < 20
        or len(raw_api_key) > 256
    ):
        raise _authentication_error()

    digest = digest_api_key(raw_api_key, settings.api_key_pepper)
    credential = session.scalar(select(AgentApiKey).where(AgentApiKey.key_digest == digest))
    if (
        credential is None
        or credential.revoked_at is not None
        or credential.agent.status != "active"
    ):
        raise _authentication_error()

    now = datetime.now(UTC)
    credential.last_used_at = now
    credential.agent.last_seen_at = now
    session.commit()
    request.state.agent_id = str(credential.agent.id)
    return credential.agent


CurrentAgentDep = Annotated[Agent, Depends(get_current_agent)]
