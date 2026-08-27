from __future__ import annotations

from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, Response, status

from agentpost.accounts.service import (
    AuthenticationFailedError,
    MfaInvalidError,
    MfaRequiredError,
    PasswordNotConfiguredError,
    verify_human_reauthentication,
)
from agentpost.api.dependencies import CurrentAgentDep, SessionDep, SettingsDep
from agentpost.control.auth import CurrentHumanDep, OptionalHumanAccessKeyDep
from agentpost.control.human_security import (
    HUMAN_CONFIRMATION_HEADER,
    HumanConfirmationInvalidError,
    HumanCsrfDep,
    add_human_action_audit,
    create_human_confirmation,
    human_session_id_from_request,
)
from agentpost.onboarding.schemas import (
    ConnectorConfirmationCreate,
    ConnectorConfirmationResponse,
    ConnectorCredentialRotationResponse,
    ConnectorHeartbeatCreate,
    ConnectorHeartbeatResponse,
    OrbitConnectorList,
    PairingConfirmationCreate,
    PairingConfirmationResponse,
    PairingCreate,
    PairingCreateResponse,
    PairingDecisionCreate,
    PairingDecisionResponse,
    PairingPreview,
    PairingTokenRequest,
    PairingTokenResponse,
)
from agentpost.onboarding.service import (
    ConnectorInvalidStateError,
    ConnectorNotFoundError,
    PairingAddressConflictError,
    PairingDeniedError,
    PairingDisabledError,
    PairingExpiredError,
    PairingHandleConflictError,
    PairingIdempotencyConflictError,
    PairingInvalidIdempotencyKeyError,
    PairingInvalidStateError,
    PairingNotFoundError,
    PairingSlowDownError,
    PairingTargetAgentMismatchError,
    PairingTargetAgentNotFoundError,
    create_pairing,
    decide_pairing,
    get_owned_connector,
    get_pairing_for_human,
    issue_pairing_token,
    list_human_connectors,
    pairing_decision_response,
    pairing_preview,
    record_connector_heartbeat,
    revoke_connector,
    rotate_connector_credential,
    verify_pairing_user_code,
)
from agentpost.security.rate_limit import (
    client_rate_limit_subject,
    enforce_http_rate_limit,
)

router = APIRouter(prefix="/api/v1", tags=["agent-onboarding"])


def _pairing_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "pairing_not_found", "message": "Pairing session was not found"},
    )


def _connector_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "connector_not_found", "message": "Connector was not found"},
    )


def _pairing_disabled() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "pairing_not_available", "message": "Agent pairing is not available"},
    )


def _pairing_invalid_state(state_value: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "pairing_invalid_state",
            "message": "The pairing cannot make this state transition",
            "details": {"status": state_value},
        },
    )


def _request_connector_instance_id(request: Request) -> UUID | None:
    value = getattr(request.state, "connector_instance_id", None)
    return UUID(value) if isinstance(value, str) else None


def _record_denied(
    request: Request,
    session: SessionDep,
    current_human: CurrentHumanDep,
    *,
    target_type: str,
    target_id: str,
    reason_code: str,
) -> None:
    human_id = current_human.id
    human_session_id = human_session_id_from_request(request)
    session.rollback()
    add_human_action_audit(
        session,
        human_user_id=human_id,
        human_session_id=human_session_id,
        action="onboarding.action_denied",
        target_type=target_type,
        target_id=target_id,
        outcome="denied",
        reason_code=reason_code,
        request_id=request.state.request_id,
    )
    session.commit()


def _verify_reauthentication(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    current_human: CurrentHumanDep,
    access_key_human: OptionalHumanAccessKeyDep,
    *,
    password: str | None,
    totp_code: str | None,
    recovery_code: str | None,
    target_type: str,
    target_id: str,
) -> None:
    if access_key_human is not None and access_key_human.id != current_human.id:
        _record_denied(
            request,
            session,
            current_human,
            target_type=target_type,
            target_id=target_id,
            reason_code="human_reauthentication_mismatch",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "human_reauthentication_failed",
                "message": "Current Human credentials and MFA proof are required",
            },
        )
    try:
        verify_human_reauthentication(
            session,
            settings,
            user=current_human,
            access_key_user=access_key_human,
            password=password,
            totp_code=totp_code,
            recovery_code=recovery_code,
        )
    except (
        AuthenticationFailedError,
        MfaRequiredError,
        MfaInvalidError,
        PasswordNotConfiguredError,
    ) as exc:
        _record_denied(
            request,
            session,
            current_human,
            target_type=target_type,
            target_id=target_id,
            reason_code="human_reauthentication_failed",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "human_reauthentication_failed",
                "message": "Current Human credentials and MFA proof are required",
            },
        ) from exc


@router.post(
    "/connect/pairings",
    response_model=PairingCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def connector_create_pairing(
    payload: PairingCreate,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
) -> PairingCreateResponse:
    if not settings.pairing_enabled:
        raise _pairing_disabled()
    enforce_http_rate_limit(
        request,
        session,
        settings,
        scope="pairing_create_ip",
        subject=client_rate_limit_subject(request),
        limit=settings.pairing_create_ip_limit,
        window_seconds=settings.pairing_rate_window_seconds,
    )
    try:
        created = create_pairing(
            session,
            settings,
            payload=payload,
            request_id=request.state.request_id,
        )
    except PairingDisabledError as exc:
        raise _pairing_disabled() from exc
    verification_uri = f"{settings.public_base_url}/orbit"
    response.headers["Cache-Control"] = "no-store"
    return PairingCreateResponse(
        pairing_id=created.pairing.pairing_id,
        device_code=created.device_code,
        user_code=created.user_code,
        verification_uri=verification_uri,
        verification_uri_complete=(
            f"{verification_uri}?pairing={quote(created.pairing.pairing_id)}"
            f"&code={quote(created.user_code)}"
        ),
        expires_at=created.pairing.expires_at,
        interval=settings.pairing_poll_interval_seconds,
    )


@router.post("/connect/pairings/token", response_model=PairingTokenResponse)
def connector_poll_pairing(
    payload: PairingTokenRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
) -> PairingTokenResponse:
    response.headers["Cache-Control"] = "no-store"
    if not settings.pairing_enabled:
        raise _pairing_disabled()
    enforce_http_rate_limit(
        request,
        session,
        settings,
        scope="pairing_poll_ip",
        subject=client_rate_limit_subject(request),
        limit=settings.pairing_poll_ip_limit,
        window_seconds=settings.pairing_rate_window_seconds,
    )
    try:
        result = issue_pairing_token(
            session,
            settings,
            device_code=payload.device_code,
            request_id=request.state.request_id,
        )
    except PairingDisabledError as exc:
        raise _pairing_disabled() from exc
    except PairingNotFoundError as exc:
        raise _pairing_not_found() from exc
    except PairingExpiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={"code": "pairing_expired", "message": "Pairing session has expired"},
        ) from exc
    except PairingDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "pairing_denied", "message": "Pairing was denied or revoked"},
        ) from exc
    except PairingSlowDownError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "pairing_slow_down", "message": "Pairing polling is too frequent"},
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    except PairingInvalidStateError as exc:
        raise _pairing_invalid_state(str(exc)) from exc
    if result.status == "pending":
        response.status_code = status.HTTP_202_ACCEPTED
        response.headers["Retry-After"] = str(result.interval)
    return result


@router.post("/connect/heartbeat", response_model=ConnectorHeartbeatResponse)
def connector_heartbeat(
    payload: ConnectorHeartbeatCreate,
    request: Request,
    response: Response,
    current_agent: CurrentAgentDep,
    session: SessionDep,
    settings: SettingsDep,
) -> ConnectorHeartbeatResponse:
    try:
        result = record_connector_heartbeat(
            session,
            settings,
            agent=current_agent,
            connector_instance_id=_request_connector_instance_id(request),
            payload=payload,
        )
    except (ConnectorNotFoundError, ConnectorInvalidStateError) as exc:
        raise _pairing_invalid_state("connector_not_current") from exc
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post(
    "/connect/credentials/rotate",
    response_model=ConnectorCredentialRotationResponse,
)
def connector_rotate_credential(
    request: Request,
    response: Response,
    current_agent: CurrentAgentDep,
    session: SessionDep,
    settings: SettingsDep,
) -> ConnectorCredentialRotationResponse:
    credential_id = getattr(request.state, "agent_api_key_id", None)
    if not isinstance(credential_id, str):
        raise _pairing_invalid_state("credential_not_current")
    try:
        result = rotate_connector_credential(
            session,
            settings,
            agent=current_agent,
            connector_instance_id=_request_connector_instance_id(request),
            agent_api_key_id=UUID(credential_id),
            request_id=request.state.request_id,
        )
    except (ConnectorNotFoundError, ConnectorInvalidStateError) as exc:
        raise _pairing_invalid_state("credential_not_current") from exc
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/orbit/pairings/{pairing_id}", response_model=PairingPreview)
def orbit_pairing_preview(
    pairing_id: str,
    response: Response,
    session: SessionDep,
    current_human: CurrentHumanDep,
) -> PairingPreview:
    try:
        pairing = get_pairing_for_human(
            session,
            user=current_human,
            pairing_id=pairing_id,
        )
    except PairingNotFoundError as exc:
        raise _pairing_not_found() from exc
    response.headers["Cache-Control"] = "no-store"
    return pairing_preview(session, pairing)


@router.post(
    "/orbit/pairings/{pairing_id}/confirmation",
    response_model=PairingConfirmationResponse,
)
def orbit_create_pairing_confirmation(
    pairing_id: str,
    payload: PairingConfirmationCreate,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    current_human: CurrentHumanDep,
    reauthenticated_human: OptionalHumanAccessKeyDep,
    csrf_guard: HumanCsrfDep,
) -> PairingConfirmationResponse:
    del csrf_guard
    _verify_reauthentication(
        request,
        session,
        settings,
        current_human,
        reauthenticated_human,
        password=payload.password.get_secret_value() if payload.password else None,
        totp_code=payload.totp_code,
        recovery_code=payload.recovery_code,
        target_type="agent_pairing",
        target_id=pairing_id,
    )
    try:
        pairing = get_pairing_for_human(
            session,
            user=current_human,
            pairing_id=pairing_id,
            for_update=True,
        )
    except PairingNotFoundError as exc:
        raise _pairing_not_found() from exc
    if pairing.status != "pending":
        raise _pairing_invalid_state(pairing.status)
    if not verify_pairing_user_code(
        pairing,
        user_code=payload.user_code,
        settings=settings,
    ):
        _record_denied(
            request,
            session,
            current_human,
            target_type="agent_pairing",
            target_id=pairing_id,
            reason_code="pairing_user_code_invalid",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "pairing_code_invalid", "message": "Pairing code is invalid"},
        )
    created = create_human_confirmation(
        session,
        settings,
        user=current_human,
        human_session_id=human_session_id_from_request(request),
        intent=f"pairing.{payload.intent}",
        target_type="agent_pairing",
        target_id=pairing.pairing_id,
        request_id=request.state.request_id,
    )
    response.headers["Cache-Control"] = "no-store"
    return PairingConfirmationResponse(
        confirmation_token=created.raw_token,
        pairing_id=pairing.pairing_id,
        intent=payload.intent,
        expires_at=created.expires_at,
    )


@router.post(
    "/orbit/pairings/{pairing_id}/decision",
    response_model=PairingDecisionResponse,
)
def orbit_decide_pairing(
    pairing_id: str,
    payload: PairingDecisionCreate,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    current_human: CurrentHumanDep,
    csrf_guard: HumanCsrfDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    confirmation_token: Annotated[
        str | None,
        Header(alias=HUMAN_CONFIRMATION_HEADER),
    ] = None,
) -> PairingDecisionResponse:
    del csrf_guard
    if confirmation_token is None:
        _record_denied(
            request,
            session,
            current_human,
            target_type="agent_pairing",
            target_id=pairing_id,
            reason_code="human_confirmation_missing",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "human_confirmation_required",
                "message": "A current one-time Human confirmation is required",
            },
        )
    try:
        result = decide_pairing(
            session,
            settings,
            user=current_human,
            human_session_id=human_session_id_from_request(request),
            pairing_id=pairing_id,
            payload=payload,
            raw_confirmation=confirmation_token,
            idempotency_key=idempotency_key,
            request_id=request.state.request_id,
        )
    except PairingNotFoundError as exc:
        raise _pairing_not_found() from exc
    except HumanConfirmationInvalidError as exc:
        _record_denied(
            request,
            session,
            current_human,
            target_type="agent_pairing",
            target_id=pairing_id,
            reason_code="human_confirmation_invalid",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "human_confirmation_invalid",
                "message": "The Human confirmation is invalid, expired, or already used",
            },
        ) from exc
    except PairingAddressConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "agent_address_conflict",
                "message": "The requested Agent address is already registered",
            },
        ) from exc
    except PairingHandleConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "handle_already_registered",
                "message": "This short Agent name is already in use",
                "details": {"handle": exc.handle, "suggestions": exc.suggestions},
            },
        ) from exc
    except PairingTargetAgentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "agent_not_owned",
                "message": "The selected Agent is not owned by the current Human",
            },
        ) from exc
    except PairingTargetAgentMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "pairing_target_mismatch",
                "message": "This pairing was started for a different existing Agent",
            },
        ) from exc
    except PairingInvalidStateError as exc:
        raise _pairing_invalid_state(str(exc)) from exc
    except PairingInvalidIdempotencyKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_idempotency_key", "message": str(exc)},
        ) from exc
    except PairingIdempotencyConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "idempotency_conflict",
                "message": "The idempotency key was already used for another decision",
            },
        ) from exc
    if result.replayed:
        response.headers["Idempotency-Replayed"] = "true"
    response.headers["Cache-Control"] = "no-store"
    return pairing_decision_response(session, result.pairing)


@router.get("/orbit/connectors", response_model=OrbitConnectorList)
def orbit_list_connectors(
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    current_human: CurrentHumanDep,
) -> OrbitConnectorList:
    response.headers["Cache-Control"] = "no-store"
    return OrbitConnectorList(
        items=list_human_connectors(
            session,
            user=current_human,
            heartbeat_interval_seconds=settings.connector_heartbeat_interval_seconds,
        )
    )


@router.post(
    "/orbit/connectors/{connector_id}/confirmation",
    response_model=ConnectorConfirmationResponse,
)
def orbit_create_connector_confirmation(
    connector_id: str,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    current_human: CurrentHumanDep,
    reauthenticated_human: OptionalHumanAccessKeyDep,
    csrf_guard: HumanCsrfDep,
    payload: ConnectorConfirmationCreate | None = None,
) -> ConnectorConfirmationResponse:
    del csrf_guard
    proof = payload or ConnectorConfirmationCreate()
    _verify_reauthentication(
        request,
        session,
        settings,
        current_human,
        reauthenticated_human,
        password=proof.password.get_secret_value() if proof.password else None,
        totp_code=proof.totp_code,
        recovery_code=proof.recovery_code,
        target_type="connector_instance",
        target_id=connector_id,
    )
    try:
        connector = get_owned_connector(
            session,
            user=current_human,
            connector_id=connector_id,
            for_update=True,
        )
    except ConnectorNotFoundError as exc:
        raise _connector_not_found() from exc
    if connector.status != "active":
        raise _pairing_invalid_state(connector.status)
    created = create_human_confirmation(
        session,
        settings,
        user=current_human,
        human_session_id=human_session_id_from_request(request),
        intent="connector.revoke",
        target_type="connector_instance",
        target_id=connector.connector_id,
        request_id=request.state.request_id,
    )
    response.headers["Cache-Control"] = "no-store"
    return ConnectorConfirmationResponse(
        confirmation_token=created.raw_token,
        connector_id=connector.connector_id,
        expires_at=created.expires_at,
    )


@router.delete(
    "/orbit/connectors/{connector_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def orbit_revoke_connector(
    connector_id: str,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    current_human: CurrentHumanDep,
    csrf_guard: HumanCsrfDep,
    confirmation_token: Annotated[
        str | None,
        Header(alias=HUMAN_CONFIRMATION_HEADER),
    ] = None,
) -> None:
    del csrf_guard
    if confirmation_token is None:
        _record_denied(
            request,
            session,
            current_human,
            target_type="connector_instance",
            target_id=connector_id,
            reason_code="human_confirmation_missing",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "human_confirmation_required",
                "message": "A current one-time Human confirmation is required",
            },
        )
    try:
        revoke_connector(
            session,
            settings,
            user=current_human,
            human_session_id=human_session_id_from_request(request),
            connector_id=connector_id,
            raw_confirmation=confirmation_token,
            request_id=request.state.request_id,
        )
    except ConnectorNotFoundError as exc:
        raise _connector_not_found() from exc
    except ConnectorInvalidStateError as exc:
        raise _pairing_invalid_state(str(exc)) from exc
    except HumanConfirmationInvalidError as exc:
        _record_denied(
            request,
            session,
            current_human,
            target_type="connector_instance",
            target_id=connector_id,
            reason_code="human_confirmation_invalid",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "human_confirmation_invalid",
                "message": "The Human confirmation is invalid, expired, or already used",
            },
        ) from exc
