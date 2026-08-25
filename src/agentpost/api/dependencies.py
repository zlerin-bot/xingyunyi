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
from agentpost.oauth.auth import resolve_access_token
from agentpost.oauth.constants import MESSAGING_SCOPE
from agentpost.oauth.crypto import ACCESS_TOKEN_MARKER
from agentpost.onboarding.models import ConnectorInstance


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


def _oauth_scope_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "insufficient_scope", "message": "The OAuth token lacks this scope"},
        headers={"WWW-Authenticate": f'Bearer scope="{MESSAGING_SCOPE}"'},
    )


def _oauth_path_allowed(request: Request, scopes: set[str]) -> bool:
    if MESSAGING_SCOPE not in scopes:
        return False
    path = request.url.path
    method = request.method.upper()
    if method == "GET" and path in {
        "/api/v1/inbox",
        "/api/v1/directory/search",
        "/api/v1/oauth/token-info",
    }:
        return True
    if path.startswith("/api/v1/messages/"):
        if method == "GET" and path.count("/") == 4:
            return True
        if method == "POST" and path.rsplit("/", 1)[-1] in {"read", "ack", "reply"}:
            return True
    return method == "POST" and path in {
        "/api/v1/messages",
        "/api/v1/directory/resolve",
    }


def get_current_agent(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> Agent:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _authentication_error()

    raw_api_key = credentials.credentials
    if raw_api_key.startswith(ACCESS_TOKEN_MARKER):
        resolved = resolve_access_token(session, settings, raw_token=raw_api_key)
        if resolved is None:
            raise _authentication_error()
        oauth_token, agent, connector = resolved
        scopes = set(oauth_token.scope.split())
        if not _oauth_path_allowed(request, scopes):
            raise _oauth_scope_error()
        now = datetime.now(UTC)
        oauth_token.last_used_at = now
        agent.last_seen_at = now
        connector.last_seen_at = now
        session.commit()
        request.state.agent_id = str(agent.id)
        request.state.agent_api_key_id = None
        request.state.connector_instance_id = str(connector.id)
        request.state.agent_credential_kind = "oauth_access"
        request.state.oauth_client_id = oauth_token.client_id
        request.state.oauth_scope = oauth_token.scope
        request.state.oauth_resource = oauth_token.resource
        request.state.oauth_expires_at = oauth_token.expires_at
        return agent
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
    if credential.connector_instance_id is not None:
        connector = session.get(ConnectorInstance, credential.connector_instance_id)
        if connector is not None and connector.status == "active":
            connector.last_seen_at = now
    session.commit()
    request.state.agent_id = str(credential.agent.id)
    request.state.agent_api_key_id = str(credential.id)
    request.state.connector_instance_id = (
        str(credential.connector_instance_id)
        if credential.connector_instance_id is not None
        else None
    )
    request.state.agent_credential_kind = "agent_api_key"
    return credential.agent


CurrentAgentDep = Annotated[Agent, Depends(get_current_agent)]
