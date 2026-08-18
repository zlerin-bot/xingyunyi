from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from agentpost.config import Settings
from agentpost.control.models import AgentOwnership, HumanUser
from agentpost.identity.models import Agent, utc_now
from agentpost.messaging.models import AuditLog
from agentpost.oauth.constants import (
    MESSAGING_SCOPE,
    OFFICIAL_REMOTE_MCP_CLIENT_ID,
)
from agentpost.oauth.crypto import (
    REFRESH_TOKEN_MARKER,
    derive_device_access_token,
    derive_device_refresh_token,
    digest_oauth_token,
    generate_access_token,
    generate_refresh_token,
    token_prefix,
)
from agentpost.oauth.models import OAuthAccessToken, OAuthRefreshToken
from agentpost.oauth.schemas import OAuthTokenResponse
from agentpost.onboarding.models import (
    AgentConnectorBinding,
    AgentPairingSession,
    ConnectorInstance,
)
from agentpost.onboarding.schemas import PairingCreate
from agentpost.onboarding.service import CreatedPairing, create_pairing


class OAuthDisabledError(Exception):
    pass


class OAuthInvalidClientError(Exception):
    pass


class OAuthInvalidTargetError(Exception):
    pass


class OAuthInvalidScopeError(Exception):
    pass


class OAuthAuthorizationPendingError(Exception):
    pass


class OAuthSlowDownError(Exception):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after


class OAuthAccessDeniedError(Exception):
    pass


class OAuthExpiredTokenError(Exception):
    pass


class OAuthInvalidGrantError(Exception):
    pass


class OAuthAgentNotOwnedError(Exception):
    pass


@dataclass(frozen=True)
class OAuthTokenRecord:
    response: OAuthTokenResponse
    access: OAuthAccessToken
    refresh: OAuthRefreshToken


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def oauth_resource(settings: Settings) -> str:
    return settings.remote_mcp_resource_url or f"{settings.public_base_url}/mcp"


def _validate_client_scope_resource(
    settings: Settings,
    *,
    client_id: str,
    scope: str,
    resource: str | None,
) -> tuple[str, str]:
    if not settings.remote_mcp_oauth_enabled:
        raise OAuthDisabledError
    if client_id != OFFICIAL_REMOTE_MCP_CLIENT_ID:
        raise OAuthInvalidClientError
    normalized_scope = " ".join(sorted(set(scope.split())))
    if normalized_scope != MESSAGING_SCOPE:
        raise OAuthInvalidScopeError
    expected_resource = oauth_resource(settings)
    if resource is not None and resource.rstrip("/") != expected_resource:
        raise OAuthInvalidTargetError
    return normalized_scope, expected_resource


def create_device_authorization(
    session: Session,
    settings: Settings,
    *,
    client_id: str,
    scope: str,
    resource: str | None,
    request_id: str,
) -> CreatedPairing:
    normalized_scope, target = _validate_client_scope_resource(
        settings,
        client_id=client_id,
        scope=scope,
        resource=resource,
    )
    return create_pairing(
        session,
        settings,
        payload=PairingCreate(
            connector_type="remote_mcp",
            display_name="Remote MCP Connector",
            capabilities=["agentpost-messaging"],
        ),
        request_id=request_id,
        credential_mode="oauth",
        oauth_client_id=client_id,
        oauth_scope=normalized_scope,
        oauth_resource=target,
    )


def _token_response(
    settings: Settings,
    *,
    access_token: str,
    refresh_token: str,
    scope: str,
    resource: str,
) -> OAuthTokenResponse:
    return OAuthTokenResponse(
        access_token=access_token,
        expires_in=settings.oauth_access_token_ttl_seconds,
        refresh_token=refresh_token,
        scope=scope,
        resource=resource,
    )


def _create_token_rows(
    session: Session,
    settings: Settings,
    *,
    pairing: AgentPairingSession | None,
    connector: ConnectorInstance,
    human_user_id: UUID,
    client_id: str,
    scope: str,
    resource: str,
    access_token: str,
    refresh_token: str,
    family_id: UUID,
    request_id: str,
    audit_action: str,
) -> OAuthTokenRecord:
    now = utc_now()
    access = OAuthAccessToken(
        token_digest=digest_oauth_token(access_token, settings.oauth_token_pepper),
        token_prefix=token_prefix(access_token),
        agent_id=connector.agent_id,
        human_user_id=human_user_id,
        connector_instance_id=connector.id,
        pairing_session_id=pairing.id if pairing else None,
        refresh_family_id=family_id,
        client_id=client_id,
        scope=scope,
        resource=resource,
        issued_at=now,
        expires_at=now + timedelta(seconds=settings.oauth_access_token_ttl_seconds),
    )
    refresh = OAuthRefreshToken(
        token_digest=digest_oauth_token(refresh_token, settings.oauth_token_pepper),
        token_prefix=token_prefix(refresh_token),
        family_id=family_id,
        agent_id=connector.agent_id,
        human_user_id=human_user_id,
        connector_instance_id=connector.id,
        pairing_session_id=pairing.id if pairing else None,
        client_id=client_id,
        scope=scope,
        resource=resource,
        issued_at=now,
        expires_at=now + timedelta(seconds=settings.oauth_refresh_token_ttl_seconds),
    )
    session.add_all([access, refresh])
    session.flush()
    session.add(
        AuditLog(
            actor_agent_id=connector.agent_id,
            action=audit_action,
            target_type="oauth_access_token",
            target_id=str(access.id),
            outcome="success",
            request_id=request_id,
            audit_metadata={
                "client_id": client_id,
                "scope": scope,
                "resource": resource,
                "connector_id": connector.connector_id,
                "refresh_family_id": str(family_id),
            },
            created_at=now,
        )
    )
    return OAuthTokenRecord(
        response=_token_response(
            settings,
            access_token=access_token,
            refresh_token=refresh_token,
            scope=scope,
            resource=resource,
        ),
        access=access,
        refresh=refresh,
    )


def exchange_device_code(
    session: Session,
    settings: Settings,
    *,
    client_id: str,
    device_code: str,
    request_id: str,
) -> OAuthTokenResponse:
    if not settings.remote_mcp_oauth_enabled:
        raise OAuthDisabledError
    if client_id != OFFICIAL_REMOTE_MCP_CLIENT_ID:
        raise OAuthInvalidClientError

    from agentpost.onboarding.crypto import pairing_digest

    digest = pairing_digest(device_code, settings.pairing_secret)
    pairing = session.scalar(
        select(AgentPairingSession)
        .where(AgentPairingSession.device_code_digest == digest)
        .with_for_update()
    )
    if (
        pairing is None
        or pairing.credential_mode != "oauth"
        or pairing.oauth_client_id != client_id
    ):
        raise OAuthInvalidGrantError
    now = utc_now()
    if _as_utc(pairing.expires_at) <= now:
        if pairing.status in {"pending", "approved"}:
            pairing.status = "expired"
            pairing.updated_at = now
            session.commit()
        raise OAuthExpiredTokenError
    if pairing.status == "denied":
        raise OAuthAccessDeniedError
    if pairing.status == "pending":
        if pairing.last_polled_at is not None:
            elapsed = (now - _as_utc(pairing.last_polled_at)).total_seconds()
            if elapsed < settings.pairing_poll_interval_seconds:
                retry_after = max(1, math.ceil(settings.pairing_poll_interval_seconds - elapsed))
                pairing.last_polled_at = now
                pairing.updated_at = now
                session.commit()
                raise OAuthSlowDownError(retry_after)
        pairing.last_polled_at = now
        pairing.updated_at = now
        session.commit()
        raise OAuthAuthorizationPendingError
    if pairing.agent_id is None or pairing.connector_instance_id is None:
        raise OAuthInvalidGrantError
    connector = session.get(ConnectorInstance, pairing.connector_instance_id)
    binding = session.get(AgentConnectorBinding, pairing.agent_id)
    if (
        connector is None
        or connector.status != "active"
        or binding is None
        or binding.connector_instance_id != connector.id
        or pairing.decided_by_human_id is None
        or pairing.oauth_scope is None
        or pairing.oauth_resource is None
    ):
        raise OAuthInvalidGrantError

    access_token = derive_device_access_token(
        device_code, connector.connector_id, settings.oauth_token_pepper
    )
    refresh_token = derive_device_refresh_token(
        device_code, connector.connector_id, settings.oauth_token_pepper
    )
    access_digest = digest_oauth_token(access_token, settings.oauth_token_pepper)
    refresh_digest = digest_oauth_token(refresh_token, settings.oauth_token_pepper)
    if pairing.status == "consumed":
        access = session.scalar(
            select(OAuthAccessToken).where(OAuthAccessToken.token_digest == access_digest)
        )
        refresh = session.scalar(
            select(OAuthRefreshToken).where(OAuthRefreshToken.token_digest == refresh_digest)
        )
        if (
            access is None
            or refresh is None
            or access.revoked_at is not None
            or refresh.revoked_at is not None
            or refresh.consumed_at is not None
        ):
            raise OAuthInvalidGrantError
        return _token_response(
            settings,
            access_token=access_token,
            refresh_token=refresh_token,
            scope=pairing.oauth_scope,
            resource=pairing.oauth_resource,
        )
    if pairing.status != "approved":
        raise OAuthInvalidGrantError

    record = _create_token_rows(
        session,
        settings,
        pairing=pairing,
        connector=connector,
        human_user_id=pairing.decided_by_human_id,
        client_id=client_id,
        scope=pairing.oauth_scope,
        resource=pairing.oauth_resource,
        access_token=access_token,
        refresh_token=refresh_token,
        family_id=uuid4(),
        request_id=request_id,
        audit_action="oauth.device_token_issued",
    )
    pairing.status = "consumed"
    pairing.credential_delivered_at = pairing.credential_delivered_at or now
    pairing.updated_at = now
    session.commit()
    return record.response


def _revoke_family(session: Session, family_id: UUID, *, reason: str) -> None:
    now = utc_now()
    for access in session.scalars(
        select(OAuthAccessToken).where(OAuthAccessToken.refresh_family_id == family_id)
    ).all():
        access.revoked_at = access.revoked_at or now
    for refresh in session.scalars(
        select(OAuthRefreshToken).where(OAuthRefreshToken.family_id == family_id)
    ).all():
        refresh.revoked_at = refresh.revoked_at or now
        refresh.revocation_reason = refresh.revocation_reason or reason


def refresh_access_token(
    session: Session,
    settings: Settings,
    *,
    client_id: str,
    raw_refresh_token: str,
    request_id: str,
) -> OAuthTokenResponse:
    if not settings.remote_mcp_oauth_enabled:
        raise OAuthDisabledError
    if client_id != OFFICIAL_REMOTE_MCP_CLIENT_ID:
        raise OAuthInvalidClientError
    if not raw_refresh_token.startswith(REFRESH_TOKEN_MARKER):
        raise OAuthInvalidGrantError
    digest = digest_oauth_token(raw_refresh_token, settings.oauth_token_pepper)
    refresh = session.scalar(
        select(OAuthRefreshToken).where(OAuthRefreshToken.token_digest == digest).with_for_update()
    )
    if refresh is None or refresh.client_id != client_id:
        raise OAuthInvalidGrantError
    if refresh.consumed_at is not None:
        _revoke_family(session, refresh.family_id, reason="replayed")
        session.commit()
        raise OAuthInvalidGrantError
    now = utc_now()
    if refresh.revoked_at is not None or _as_utc(refresh.expires_at) <= now:
        raise OAuthInvalidGrantError
    connector = session.get(ConnectorInstance, refresh.connector_instance_id)
    binding = session.get(AgentConnectorBinding, refresh.agent_id)
    if (
        connector is None
        or connector.status != "active"
        or binding is None
        or binding.connector_instance_id != connector.id
    ):
        _revoke_family(session, refresh.family_id, reason="connector_replaced")
        session.commit()
        raise OAuthInvalidGrantError

    _revoke_family(session, refresh.family_id, reason="rotated")
    refresh.consumed_at = now
    access_token = generate_access_token()
    next_refresh_token = generate_refresh_token()
    record = _create_token_rows(
        session,
        settings,
        pairing=None,
        connector=connector,
        human_user_id=refresh.human_user_id,
        client_id=refresh.client_id,
        scope=refresh.scope,
        resource=refresh.resource,
        access_token=access_token,
        refresh_token=next_refresh_token,
        family_id=refresh.family_id,
        request_id=request_id,
        audit_action="oauth.access_token_refreshed",
    )
    session.commit()
    return record.response


def owned_agent(session: Session, *, user: HumanUser, agent_id: UUID) -> Agent:
    agent = session.scalar(
        select(Agent)
        .join(AgentOwnership, AgentOwnership.agent_id == Agent.id)
        .where(
            Agent.id == agent_id,
            AgentOwnership.human_user_id == user.id,
            Agent.status == "active",
        )
    )
    if agent is None:
        raise OAuthAgentNotOwnedError
    return agent


def revoke_connector_oauth_tokens(
    session: Session,
    connector_instance_id: UUID,
    *,
    reason: str,
) -> None:
    now = utc_now()
    for access in session.scalars(
        select(OAuthAccessToken).where(
            OAuthAccessToken.connector_instance_id == connector_instance_id,
            OAuthAccessToken.revoked_at.is_(None),
        )
    ).all():
        access.revoked_at = now
    for refresh in session.scalars(
        select(OAuthRefreshToken).where(
            OAuthRefreshToken.connector_instance_id == connector_instance_id,
            OAuthRefreshToken.revoked_at.is_(None),
        )
    ).all():
        refresh.revoked_at = now
        refresh.revocation_reason = reason
