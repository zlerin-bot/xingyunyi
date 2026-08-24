from __future__ import annotations

import hashlib
import hmac
import json
import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agentpost.config import Settings
from agentpost.control.human_security import consume_human_confirmation
from agentpost.control.models import AgentOwnership, HumanUser
from agentpost.identity.addressing import (
    address_domain,
    address_local_id,
    canonicalize_agent_address,
)
from agentpost.identity.api_keys import api_key_prefix, digest_api_key, generate_api_key
from agentpost.identity.models import Agent, AgentApiKey, utc_now
from agentpost.messaging.models import AuditLog
from agentpost.onboarding.crypto import (
    canonicalize_user_code,
    derive_agent_api_key,
    generate_connector_id,
    generate_device_code,
    generate_pairing_id,
    generate_user_code,
    pairing_digest,
)
from agentpost.onboarding.models import (
    AgentConnectorBinding,
    AgentPairingSession,
    ConnectorInstance,
)
from agentpost.onboarding.schemas import (
    ConnectorCredentialRotationResponse,
    ConnectorHeartbeatCreate,
    ConnectorHeartbeatResponse,
    OrbitConnector,
    PairingAgentResponse,
    PairingConnectorResponse,
    PairingCreate,
    PairingDecisionCreate,
    PairingDecisionResponse,
    PairingPreview,
    PairingTokenResponse,
)

_IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[\x21-\x7e]{1,255}$", flags=re.ASCII)


class PairingDisabledError(Exception):
    pass


class PairingNotFoundError(Exception):
    pass


class PairingInvalidStateError(Exception):
    pass


class PairingExpiredError(Exception):
    pass


class PairingDeniedError(Exception):
    pass


class PairingSlowDownError(Exception):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after


class PairingAddressConflictError(Exception):
    pass


class PairingTargetAgentNotFoundError(Exception):
    pass


class PairingIdempotencyConflictError(Exception):
    pass


class PairingInvalidIdempotencyKeyError(ValueError):
    pass


class ConnectorNotFoundError(Exception):
    pass


class ConnectorInvalidStateError(Exception):
    pass


@dataclass(frozen=True)
class CreatedPairing:
    pairing: AgentPairingSession
    device_code: str
    user_code: str


@dataclass(frozen=True)
class PairingDecisionResult:
    pairing: AgentPairingSession
    replayed: bool


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _validate_idempotency_key(value: str) -> str:
    if not _IDEMPOTENCY_KEY_PATTERN.fullmatch(value):
        raise PairingInvalidIdempotencyKeyError(
            "Idempotency-Key must contain 1-255 printable ASCII characters without spaces"
        )
    return value


def _decision_hash(pairing_id: str, payload: PairingDecisionCreate) -> str:
    canonical = json.dumps(
        {
            "operation": "pairing_decision",
            "pairing_id": pairing_id,
            "payload": payload.model_dump(mode="json", exclude_none=False),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def _automatic_local_agent_id(pairing: AgentPairingSession) -> str:
    connector_slug = re.sub(r"[^a-z0-9]+", "-", pairing.connector_type.lower()).strip("-")
    prefix = connector_slug or "agent"
    suffix = hashlib.sha256(pairing.pairing_id.encode("utf-8")).hexdigest()[:24]
    return f"{prefix[:39]}-{suffix}"


def _connector_response(connector: ConnectorInstance) -> PairingConnectorResponse:
    return PairingConnectorResponse(
        connector_id=connector.connector_id,
        connector_type=connector.connector_type,
        display_name=connector.display_name,
        device_name=connector.device_name,
        client_version=connector.client_version,
        status=connector.status,
        health_status=connector.health_status,
        created_at=connector.created_at,
        activated_at=connector.activated_at,
        last_seen_at=connector.last_seen_at,
        last_heartbeat_at=connector.last_heartbeat_at,
        last_error_code=connector.last_error_code,
        credential_rotated_at=connector.credential_rotated_at,
        revoked_at=connector.revoked_at,
    )


def _agent_response(agent: Agent) -> PairingAgentResponse:
    return PairingAgentResponse(
        id=agent.id,
        address=agent.address,
        display_name=agent.display_name,
    )


def pairing_preview(session: Session, pairing: AgentPairingSession) -> PairingPreview:
    agent = session.get(Agent, pairing.agent_id) if pairing.agent_id else None
    return PairingPreview(
        pairing_id=pairing.pairing_id,
        user_code_hint=pairing.user_code_hint,
        connector_type=pairing.connector_type,
        connector_display_name=pairing.connector_display_name,
        device_name=pairing.device_name,
        client_version=pairing.client_version,
        requested_capabilities=list(pairing.requested_capabilities),
        status=pairing.status,
        expires_at=pairing.expires_at,
        agent=_agent_response(agent) if agent else None,
    )


def _expire_if_needed(session: Session, pairing: AgentPairingSession) -> bool:
    if pairing.status in {"pending", "approved"} and _as_utc(pairing.expires_at) <= utc_now():
        pairing.status = "expired"
        pairing.updated_at = utc_now()
        session.commit()
        return True
    return pairing.status == "expired"


def create_pairing(
    session: Session,
    settings: Settings,
    *,
    payload: PairingCreate,
    request_id: str,
    credential_mode: str = "agent_api_key",
    oauth_client_id: str | None = None,
    oauth_scope: str | None = None,
    oauth_resource: str | None = None,
) -> CreatedPairing:
    if not settings.pairing_enabled:
        raise PairingDisabledError

    now = utc_now()
    for _ in range(3):
        device_code = generate_device_code()
        user_code = generate_user_code()
        pairing = AgentPairingSession(
            pairing_id=generate_pairing_id(),
            device_code_digest=pairing_digest(device_code, settings.pairing_secret),
            user_code_digest=pairing_digest(
                canonicalize_user_code(user_code),
                settings.pairing_secret,
            ),
            user_code_hint=f"••••-{user_code[-4:]}",
            connector_type=payload.connector_type,
            connector_display_name=payload.display_name,
            device_name=payload.device_name,
            client_version=payload.client_version,
            requested_capabilities=payload.capabilities,
            credential_mode=credential_mode,
            oauth_client_id=oauth_client_id,
            oauth_scope=oauth_scope,
            oauth_resource=oauth_resource,
            status="pending",
            expires_at=now + timedelta(seconds=settings.pairing_ttl_seconds),
            created_at=now,
            updated_at=now,
        )
        session.add(pairing)
        try:
            session.flush()
        except IntegrityError:
            session.rollback()
            continue
        session.add(
            AuditLog(
                actor_agent_id=None,
                action="onboarding.pairing_created",
                target_type="agent_pairing",
                target_id=pairing.pairing_id,
                outcome="success",
                request_id=request_id,
                audit_metadata={
                    "connector_type": pairing.connector_type,
                    "expires_at": pairing.expires_at.isoformat(),
                },
                created_at=now,
            )
        )
        session.commit()
        return CreatedPairing(pairing=pairing, device_code=device_code, user_code=user_code)
    raise RuntimeError("Unable to allocate a unique pairing session")


def get_pairing_for_human(
    session: Session,
    *,
    user: HumanUser,
    pairing_id: str,
    for_update: bool = False,
) -> AgentPairingSession:
    statement = select(AgentPairingSession).where(AgentPairingSession.pairing_id == pairing_id)
    if for_update:
        statement = statement.with_for_update()
    pairing = session.scalar(statement)
    if pairing is None or (
        pairing.decided_by_human_id is not None and pairing.decided_by_human_id != user.id
    ):
        raise PairingNotFoundError
    _expire_if_needed(session, pairing)
    return pairing


def verify_pairing_user_code(
    pairing: AgentPairingSession,
    *,
    user_code: str,
    settings: Settings,
) -> bool:
    try:
        canonical = canonicalize_user_code(user_code)
    except ValueError:
        return False
    return hmac.compare_digest(
        pairing.user_code_digest,
        pairing_digest(canonical, settings.pairing_secret),
    )


def issue_pairing_token(
    session: Session,
    settings: Settings,
    *,
    device_code: str,
    request_id: str,
) -> PairingTokenResponse:
    if not settings.pairing_enabled:
        raise PairingDisabledError
    digest = pairing_digest(device_code, settings.pairing_secret)
    pairing = session.scalar(
        select(AgentPairingSession)
        .where(AgentPairingSession.device_code_digest == digest)
        .with_for_update()
    )
    if pairing is None:
        raise PairingNotFoundError
    if pairing.credential_mode != "agent_api_key":
        raise PairingNotFoundError
    if _expire_if_needed(session, pairing):
        raise PairingExpiredError
    if pairing.status == "denied":
        raise PairingDeniedError
    if pairing.status == "pending":
        now = utc_now()
        if pairing.last_polled_at is not None:
            elapsed = (now - _as_utc(pairing.last_polled_at)).total_seconds()
            if elapsed < settings.pairing_poll_interval_seconds:
                raise PairingSlowDownError(
                    max(1, math.ceil(settings.pairing_poll_interval_seconds - elapsed))
                )
        pairing.last_polled_at = now
        pairing.updated_at = now
        session.commit()
        return PairingTokenResponse(
            status="pending",
            interval=settings.pairing_poll_interval_seconds,
        )
    if pairing.status not in {"approved", "consumed"}:
        raise PairingInvalidStateError(pairing.status)
    if pairing.agent_id is None or pairing.connector_instance_id is None:
        raise PairingInvalidStateError(pairing.status)

    agent = session.get(Agent, pairing.agent_id)
    connector = session.get(ConnectorInstance, pairing.connector_instance_id)
    binding = session.get(AgentConnectorBinding, pairing.agent_id)
    if (
        agent is None
        or connector is None
        or connector.status != "active"
        or binding is None
        or binding.connector_instance_id != connector.id
    ):
        raise PairingDeniedError

    raw_api_key = derive_agent_api_key(device_code, connector.connector_id, settings.pairing_secret)
    credential = session.scalar(
        select(AgentApiKey).where(AgentApiKey.connector_instance_id == connector.id)
    )
    now = utc_now()
    if credential is None:
        credential = AgentApiKey(
            agent_id=agent.id,
            connector_instance_id=connector.id,
            key_digest=digest_api_key(raw_api_key, settings.api_key_pepper),
            key_prefix=api_key_prefix(raw_api_key),
            created_at=now,
        )
        session.add(credential)
        session.add(
            AuditLog(
                actor_agent_id=agent.id,
                action="onboarding.connector_credential_issued",
                target_type="connector_instance",
                target_id=connector.connector_id,
                outcome="success",
                request_id=request_id,
                audit_metadata={},
                created_at=now,
            )
        )
    elif credential.revoked_at is not None:
        raise PairingDeniedError
    pairing.status = "consumed"
    pairing.credential_delivered_at = pairing.credential_delivered_at or now
    pairing.updated_at = now
    session.commit()
    return PairingTokenResponse(
        status="approved",
        interval=settings.pairing_poll_interval_seconds,
        agent=_agent_response(agent),
        connector=_connector_response(connector),
        api_key=raw_api_key,
    )


def decide_pairing(
    session: Session,
    settings: Settings,
    *,
    user: HumanUser,
    human_session_id: UUID | None,
    pairing_id: str,
    payload: PairingDecisionCreate,
    raw_confirmation: str,
    idempotency_key: str,
    request_id: str,
) -> PairingDecisionResult:
    key = _validate_idempotency_key(idempotency_key)
    request_hash = _decision_hash(pairing_id, payload)
    existing = session.scalar(
        select(AgentPairingSession).where(
            AgentPairingSession.decided_by_human_id == user.id,
            AgentPairingSession.decision_idempotency_key == key,
        )
    )
    if existing is not None:
        if existing.pairing_id == pairing_id and existing.decision_request_hash == request_hash:
            return PairingDecisionResult(pairing=existing, replayed=True)
        raise PairingIdempotencyConflictError

    pairing = get_pairing_for_human(
        session,
        user=user,
        pairing_id=pairing_id,
        for_update=True,
    )
    if pairing.status != "pending":
        if (
            pairing.decided_by_human_id == user.id
            and pairing.decision_idempotency_key == key
            and pairing.decision_request_hash == request_hash
        ):
            return PairingDecisionResult(pairing=pairing, replayed=True)
        raise PairingInvalidStateError(pairing.status)
    intent = "approve" if payload.decision == "approved" else "deny"
    consume_human_confirmation(
        session,
        settings,
        user=user,
        human_session_id=human_session_id,
        intent=f"pairing.{intent}",
        target_type="agent_pairing",
        target_id=pairing.pairing_id,
        raw_token=raw_confirmation,
    )

    now = utc_now()
    pairing.decided_by_human_id = user.id
    pairing.human_session_id = human_session_id
    pairing.decided_at = now
    pairing.updated_at = now
    pairing.decision_idempotency_key = key
    pairing.decision_request_hash = request_hash
    connector: ConnectorInstance | None = None
    previous_connector: ConnectorInstance | None = None

    if payload.decision == "denied":
        pairing.status = "denied"
    else:
        if payload.existing_agent_id is not None:
            agent = session.scalar(
                select(Agent)
                .join(AgentOwnership, AgentOwnership.agent_id == Agent.id)
                .where(
                    Agent.id == payload.existing_agent_id,
                    AgentOwnership.human_user_id == user.id,
                    Agent.status == "active",
                )
                .with_for_update()
            )
            if agent is None:
                raise PairingTargetAgentNotFoundError
        else:
            local_agent_id = (
                _automatic_local_agent_id(pairing)
                if payload.create_new_agent
                else payload.local_agent_id
            )
            assert local_agent_id is not None
            address = canonicalize_agent_address(
                f"{local_agent_id}@{settings.managed_agent_domain}"
            )
            if session.scalar(select(Agent.id).where(Agent.address == address)) is not None:
                raise PairingAddressConflictError(address)
            capabilities = (
                list(pairing.requested_capabilities)
                if payload.create_new_agent
                else (
                    payload.capabilities
                    if payload.capabilities is not None
                    else list(pairing.requested_capabilities)
                )
            )
            agent = Agent(
                address=address,
                display_name=(
                    pairing.connector_display_name
                    if payload.create_new_agent
                    else payload.display_name or address_local_id(address)
                ),
                description=None if payload.create_new_agent else payload.description,
                owner_id=str(user.id),
                domain=address_domain(address),
                status="active",
                capabilities=capabilities,
                endpoint=None,
                created_at=now,
                updated_at=now,
            )
            session.add(agent)
            session.flush()
            session.add(
                AgentOwnership(
                    agent_id=agent.id,
                    human_user_id=user.id,
                    assigned_at=now,
                )
            )
        current_binding = session.scalar(
            select(AgentConnectorBinding)
            .where(AgentConnectorBinding.agent_id == agent.id)
            .with_for_update()
        )
        previous_connector = (
            session.get(ConnectorInstance, current_binding.connector_instance_id)
            if current_binding is not None
            else None
        )
        connector = ConnectorInstance(
            connector_id=generate_connector_id(),
            agent_id=agent.id,
            human_user_id=user.id,
            connector_type=pairing.connector_type,
            display_name=pairing.connector_display_name,
            device_name=pairing.device_name,
            client_version=pairing.client_version,
            status="active",
            created_at=now,
            activated_at=now,
        )
        session.add(connector)
        session.flush()
        if current_binding is None:
            session.add(
                AgentConnectorBinding(
                    agent_id=agent.id,
                    connector_instance_id=connector.id,
                    bound_at=now,
                )
            )
        else:
            current_binding.connector_instance_id = connector.id
            current_binding.bound_at = now
        if previous_connector is not None:
            previous_connector.status = "replaced"
            previous_connector.revoked_at = now
            previous_connector.revocation_reason = "replaced_by_new_connector"
            for credential in session.scalars(
                select(AgentApiKey).where(
                    AgentApiKey.connector_instance_id == previous_connector.id
                )
            ).all():
                credential.revoked_at = credential.revoked_at or now
            from agentpost.oauth.service import revoke_connector_oauth_tokens

            revoke_connector_oauth_tokens(
                session,
                previous_connector.id,
                reason="connector_replaced",
            )
        pairing.agent_id = agent.id
        pairing.connector_instance_id = connector.id
        pairing.status = "approved"
        pairing.expires_at = now + timedelta(seconds=settings.pairing_ttl_seconds)

    from agentpost.control.human_security import add_human_action_audit

    add_human_action_audit(
        session,
        human_user_id=user.id,
        human_session_id=human_session_id,
        action="onboarding.pairing_decided",
        target_type="agent_pairing",
        target_id=pairing.pairing_id,
        outcome="success",
        request_id=request_id,
        audit_metadata={
            "decision": payload.decision,
            "target_selection": (
                "denied"
                if payload.decision == "denied"
                else (
                    "automatic_new"
                    if payload.create_new_agent
                    else "existing"
                    if payload.existing_agent_id
                    else "explicit_new"
                )
            ),
            "agent_id": str(pairing.agent_id) if pairing.agent_id else None,
            "connector_id": connector.connector_id if connector else None,
            "replaces_connector_id": (
                previous_connector.connector_id if previous_connector else None
            ),
        },
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise PairingAddressConflictError(payload.local_agent_id or "automatic") from exc
    return PairingDecisionResult(pairing=pairing, replayed=False)


def pairing_decision_response(
    session: Session,
    pairing: AgentPairingSession,
) -> PairingDecisionResponse:
    connector = (
        session.get(ConnectorInstance, pairing.connector_instance_id)
        if pairing.connector_instance_id
        else None
    )
    return PairingDecisionResponse(
        pairing=pairing_preview(session, pairing),
        connector=_connector_response(connector) if connector else None,
    )


def list_human_connectors(session: Session, *, user: HumanUser) -> list[OrbitConnector]:
    rows = session.execute(
        select(ConnectorInstance, Agent)
        .join(Agent, Agent.id == ConnectorInstance.agent_id)
        .join(AgentOwnership, AgentOwnership.agent_id == Agent.id)
        .where(AgentOwnership.human_user_id == user.id)
        .order_by(Agent.address, ConnectorInstance.created_at.desc())
    ).all()
    bindings = {
        binding.connector_instance_id
        for binding in session.scalars(
            select(AgentConnectorBinding).where(
                AgentConnectorBinding.agent_id.in_([agent.id for _, agent in rows])
            )
        ).all()
    }
    return [
        OrbitConnector(
            **_connector_response(connector).model_dump(),
            agent=_agent_response(agent),
            is_current=connector.id in bindings,
        )
        for connector, agent in rows
    ]


def get_owned_connector(
    session: Session,
    *,
    user: HumanUser,
    connector_id: str,
    for_update: bool = False,
) -> ConnectorInstance:
    statement = (
        select(ConnectorInstance)
        .join(AgentOwnership, AgentOwnership.agent_id == ConnectorInstance.agent_id)
        .where(
            ConnectorInstance.connector_id == connector_id,
            AgentOwnership.human_user_id == user.id,
        )
    )
    if for_update:
        statement = statement.with_for_update()
    connector = session.scalar(statement)
    if connector is None:
        raise ConnectorNotFoundError
    return connector


def revoke_connector(
    session: Session,
    settings: Settings,
    *,
    user: HumanUser,
    human_session_id: UUID | None,
    connector_id: str,
    raw_confirmation: str,
    request_id: str,
) -> None:
    connector = get_owned_connector(
        session,
        user=user,
        connector_id=connector_id,
        for_update=True,
    )
    if connector.status == "revoked":
        return
    if connector.status != "active":
        raise ConnectorInvalidStateError(connector.status)
    binding = session.scalar(
        select(AgentConnectorBinding)
        .where(AgentConnectorBinding.connector_instance_id == connector.id)
        .with_for_update()
    )
    if binding is None:
        raise ConnectorInvalidStateError(connector.status)
    consume_human_confirmation(
        session,
        settings,
        user=user,
        human_session_id=human_session_id,
        intent="connector.revoke",
        target_type="connector_instance",
        target_id=connector.connector_id,
        raw_token=raw_confirmation,
    )
    now = utc_now()
    session.delete(binding)
    connector.status = "revoked"
    connector.revoked_at = now
    connector.revocation_reason = "revoked_by_owner"
    for credential in session.scalars(
        select(AgentApiKey).where(AgentApiKey.connector_instance_id == connector.id)
    ).all():
        credential.revoked_at = credential.revoked_at or now
    from agentpost.oauth.service import revoke_connector_oauth_tokens

    revoke_connector_oauth_tokens(
        session,
        connector.id,
        reason="connector_revoked",
    )

    from agentpost.control.human_security import add_human_action_audit

    add_human_action_audit(
        session,
        human_user_id=user.id,
        human_session_id=human_session_id,
        action="onboarding.connector_revoked",
        target_type="connector_instance",
        target_id=connector.connector_id,
        outcome="success",
        request_id=request_id,
        audit_metadata={"agent_id": str(connector.agent_id)},
    )
    session.commit()


def get_current_connector(
    session: Session,
    *,
    agent: Agent,
    connector_instance_id: UUID | None,
    for_update: bool = False,
) -> ConnectorInstance:
    if connector_instance_id is None:
        raise ConnectorNotFoundError
    statement = select(ConnectorInstance).where(
        ConnectorInstance.id == connector_instance_id,
        ConnectorInstance.agent_id == agent.id,
        ConnectorInstance.status == "active",
    )
    if for_update:
        statement = statement.with_for_update()
    connector = session.scalar(statement)
    binding = session.get(AgentConnectorBinding, agent.id)
    if connector is None or binding is None or binding.connector_instance_id != connector.id:
        raise ConnectorInvalidStateError("not_current")
    return connector


def record_connector_heartbeat(
    session: Session,
    settings: Settings,
    *,
    agent: Agent,
    connector_instance_id: UUID | None,
    payload: ConnectorHeartbeatCreate,
) -> ConnectorHeartbeatResponse:
    connector = get_current_connector(
        session,
        agent=agent,
        connector_instance_id=connector_instance_id,
        for_update=True,
    )
    now = utc_now()
    connector.health_status = payload.health_status
    connector.last_heartbeat_at = now
    connector.last_seen_at = now
    connector.last_error_code = payload.last_error_code
    connector.last_error_at = now if payload.last_error_code is not None else None
    agent.last_seen_at = now
    session.commit()
    return ConnectorHeartbeatResponse(
        connector=_connector_response(connector),
        agent=_agent_response(agent),
        server_time=now,
        recommended_interval_seconds=settings.connector_heartbeat_interval_seconds,
    )


def rotate_connector_credential(
    session: Session,
    settings: Settings,
    *,
    agent: Agent,
    connector_instance_id: UUID | None,
    agent_api_key_id: UUID,
    request_id: str,
) -> ConnectorCredentialRotationResponse:
    connector = get_current_connector(
        session,
        agent=agent,
        connector_instance_id=connector_instance_id,
        for_update=True,
    )
    credential = session.scalar(
        select(AgentApiKey)
        .where(
            AgentApiKey.id == agent_api_key_id,
            AgentApiKey.agent_id == agent.id,
            AgentApiKey.connector_instance_id == connector.id,
            AgentApiKey.revoked_at.is_(None),
        )
        .with_for_update()
    )
    if credential is None:
        raise ConnectorInvalidStateError("credential_not_current")
    raw_api_key = generate_api_key()
    now = utc_now()
    credential.key_digest = digest_api_key(raw_api_key, settings.api_key_pepper)
    credential.key_prefix = api_key_prefix(raw_api_key)
    credential.created_at = now
    credential.last_used_at = None
    connector.credential_rotated_at = now
    connector.last_seen_at = now
    session.add(
        AuditLog(
            actor_agent_id=agent.id,
            action="onboarding.connector_credential_rotated",
            target_type="connector_instance",
            target_id=connector.connector_id,
            outcome="success",
            request_id=request_id,
            audit_metadata={},
            created_at=now,
        )
    )
    session.commit()
    return ConnectorCredentialRotationResponse(
        connector_id=connector.connector_id,
        agent=_agent_response(agent),
        api_key=raw_api_key,
        rotated_at=now,
    )
