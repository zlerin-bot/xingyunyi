from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from agentpost.config import Settings
from agentpost.identity.models import Agent, utc_now
from agentpost.oauth.crypto import ACCESS_TOKEN_MARKER, digest_oauth_token
from agentpost.oauth.models import OAuthAccessToken
from agentpost.onboarding.models import AgentConnectorBinding, ConnectorInstance


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def resolve_access_token(
    session: Session,
    settings: Settings,
    *,
    raw_token: str,
) -> tuple[OAuthAccessToken, Agent, ConnectorInstance] | None:
    if not raw_token.startswith(ACCESS_TOKEN_MARKER) or not 20 <= len(raw_token) <= 256:
        return None
    digest = digest_oauth_token(raw_token, settings.oauth_token_pepper)
    token = session.scalar(select(OAuthAccessToken).where(OAuthAccessToken.token_digest == digest))
    if token is None or token.revoked_at is not None or _as_utc(token.expires_at) <= utc_now():
        return None
    agent = session.get(Agent, token.agent_id)
    connector = session.get(ConnectorInstance, token.connector_instance_id)
    binding = session.get(AgentConnectorBinding, token.agent_id)
    if (
        agent is None
        or agent.status != "active"
        or connector is None
        or connector.status != "active"
        or binding is None
        or binding.connector_instance_id != connector.id
    ):
        return None
    return token, agent, connector
