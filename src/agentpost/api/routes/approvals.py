from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response, status

from agentpost.api.dependencies import CurrentAgentDep, SessionDep, SettingsDep
from agentpost.control.approval_schemas import (
    ApprovalConfirmationCreate,
    ApprovalConfirmationResponse,
    ApprovalDecisionCreate,
    ApprovalRequestCreate,
    ApprovalRequestListResponse,
    ApprovalRequestResponse,
    ApprovalStatus,
    OrbitApprovalListResponse,
    OrbitApprovalRequest,
)
from agentpost.control.approval_service import (
    ApprovalDecisionNotAllowedError,
    ApprovalIdempotencyConflictError,
    ApprovalInvalidIdempotencyKeyError,
    ApprovalInvalidStateError,
    ApprovalNotFoundError,
    approval_response,
    authorize_human_approval_decision,
    cancel_agent_approval_request,
    create_approval_request,
    decide_human_approval_request,
    get_agent_approval_request,
    get_human_approval_request,
    list_agent_approval_requests,
    list_human_approval_requests,
)
from agentpost.control.auth import CurrentHumanDep, HumanAccessKeyDep
from agentpost.control.human_security import (
    HUMAN_CONFIRMATION_HEADER,
    HumanConfirmationInvalidError,
    HumanCsrfDep,
    add_human_action_audit,
    create_human_confirmation,
    human_session_id_from_request,
)

router = APIRouter(prefix="/api/v1", tags=["approvals"])
Limit = Annotated[int, Query(ge=1, le=100)]


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "approval_not_found", "message": "Approval request was not found"},
    )


def _invalid_state(state_value: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "approval_invalid_state",
            "message": "The approval request cannot make this state transition",
            "details": {"status": state_value},
        },
    )


def _idempotency_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ApprovalInvalidIdempotencyKeyError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_idempotency_key", "message": str(exc)},
        )
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "idempotency_conflict",
            "message": "The idempotency key was already used for a different request",
        },
    )


def _record_denied(
    request: Request,
    session: SessionDep,
    current_human: CurrentHumanDep,
    *,
    approval_id: str,
    reason_code: str,
) -> None:
    human_id = current_human.id
    session_id = human_session_id_from_request(request)
    session.rollback()
    add_human_action_audit(
        session,
        human_user_id=human_id,
        human_session_id=session_id,
        action="approval.decision_denied",
        target_type="approval_request",
        target_id=approval_id,
        outcome="denied",
        reason_code=reason_code,
        request_id=request.state.request_id,
    )
    session.commit()


@router.post(
    "/approval-requests",
    response_model=ApprovalRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def agent_create_approval_request(
    payload: ApprovalRequestCreate,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    current_agent: CurrentAgentDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> ApprovalRequestResponse:
    try:
        result = create_approval_request(
            session,
            settings,
            agent=current_agent,
            payload=payload,
            idempotency_key=idempotency_key,
            request_id=request.state.request_id,
        )
    except (ApprovalInvalidIdempotencyKeyError, ApprovalIdempotencyConflictError) as exc:
        raise _idempotency_error(exc) from exc
    if result.replayed:
        response.status_code = status.HTTP_200_OK
        response.headers["Idempotency-Replayed"] = "true"
    return approval_response(session, result.approval)


@router.get(
    "/approval-requests",
    response_model=ApprovalRequestListResponse,
)
def agent_list_approval_requests(
    session: SessionDep,
    current_agent: CurrentAgentDep,
    limit: Limit = 50,
    approval_status: Annotated[ApprovalStatus | None, Query(alias="status")] = None,
) -> ApprovalRequestListResponse:
    return ApprovalRequestListResponse(
        items=list_agent_approval_requests(
            session,
            agent=current_agent,
            limit=limit,
            approval_status=approval_status,
        )
    )


@router.get(
    "/approval-requests/{approval_id}",
    response_model=ApprovalRequestResponse,
)
def agent_get_approval_request(
    approval_id: str,
    session: SessionDep,
    current_agent: CurrentAgentDep,
) -> ApprovalRequestResponse:
    try:
        return get_agent_approval_request(
            session,
            agent=current_agent,
            approval_id=approval_id,
        )
    except ApprovalNotFoundError as exc:
        raise _not_found() from exc


@router.post(
    "/approval-requests/{approval_id}/cancel",
    response_model=ApprovalRequestResponse,
)
def agent_cancel_approval_request(
    approval_id: str,
    request: Request,
    session: SessionDep,
    current_agent: CurrentAgentDep,
) -> ApprovalRequestResponse:
    try:
        return cancel_agent_approval_request(
            session,
            agent=current_agent,
            approval_id=approval_id,
            request_id=request.state.request_id,
        )
    except ApprovalNotFoundError as exc:
        raise _not_found() from exc
    except ApprovalInvalidStateError as exc:
        raise _invalid_state(str(exc)) from exc


@router.get(
    "/orbit/approval-requests",
    response_model=OrbitApprovalListResponse,
)
def orbit_list_approval_requests(
    session: SessionDep,
    current_human: CurrentHumanDep,
    limit: Limit = 50,
    approval_status: Annotated[ApprovalStatus | None, Query(alias="status")] = None,
) -> OrbitApprovalListResponse:
    return OrbitApprovalListResponse(
        items=list_human_approval_requests(
            session,
            user=current_human,
            limit=limit,
            approval_status=approval_status,
        )
    )


@router.get(
    "/orbit/approval-requests/{approval_id}",
    response_model=OrbitApprovalRequest,
)
def orbit_get_approval_request(
    approval_id: str,
    session: SessionDep,
    current_human: CurrentHumanDep,
) -> OrbitApprovalRequest:
    try:
        return get_human_approval_request(
            session,
            user=current_human,
            approval_id=approval_id,
        )
    except ApprovalNotFoundError as exc:
        raise _not_found() from exc


@router.post(
    "/orbit/approval-requests/{approval_id}/confirmation",
    response_model=ApprovalConfirmationResponse,
)
def orbit_create_approval_confirmation(
    approval_id: str,
    payload: ApprovalConfirmationCreate,
    response: Response,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    current_human: CurrentHumanDep,
    reauthenticated_human: HumanAccessKeyDep,
    csrf_guard: HumanCsrfDep,
) -> ApprovalConfirmationResponse:
    del csrf_guard
    if reauthenticated_human.id != current_human.id:
        _record_denied(
            request,
            session,
            current_human,
            approval_id=approval_id,
            reason_code="human_reauthentication_mismatch",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "human_reauthentication_failed",
                "message": "The access key does not match the active Human session",
            },
        )
    try:
        approval = authorize_human_approval_decision(
            session,
            user=current_human,
            approval_id=approval_id,
        )
    except ApprovalNotFoundError as exc:
        raise _not_found() from exc
    except ApprovalDecisionNotAllowedError as exc:
        _record_denied(
            request,
            session,
            current_human,
            approval_id=approval_id,
            reason_code="approval_decision_not_allowed",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "approval_decision_not_allowed",
                "message": "This Human role cannot decide approval requests",
            },
        ) from exc
    except ApprovalInvalidStateError as exc:
        _record_denied(
            request,
            session,
            current_human,
            approval_id=approval_id,
            reason_code="approval_invalid_state",
        )
        raise _invalid_state(str(exc)) from exc

    created = create_human_confirmation(
        session,
        settings,
        user=current_human,
        human_session_id=human_session_id_from_request(request),
        intent=f"approval.{payload.intent}",
        target_type="approval_request",
        target_id=approval.approval_id,
        request_id=request.state.request_id,
    )
    response.headers["Cache-Control"] = "no-store"
    return ApprovalConfirmationResponse(
        confirmation_token=created.raw_token,
        intent=payload.intent,
        approval_id=approval.approval_id,
        expires_at=created.expires_at,
    )


@router.post(
    "/orbit/approval-requests/{approval_id}/decision",
    response_model=OrbitApprovalRequest,
)
def orbit_decide_approval_request(
    approval_id: str,
    payload: ApprovalDecisionCreate,
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
) -> OrbitApprovalRequest:
    del csrf_guard
    if confirmation_token is None:
        _record_denied(
            request,
            session,
            current_human,
            approval_id=approval_id,
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
        result = decide_human_approval_request(
            session,
            settings,
            user=current_human,
            human_session_id=human_session_id_from_request(request),
            approval_id=approval_id,
            payload=payload,
            raw_confirmation=confirmation_token,
            idempotency_key=idempotency_key,
            request_id=request.state.request_id,
        )
    except ApprovalNotFoundError as exc:
        raise _not_found() from exc
    except ApprovalDecisionNotAllowedError as exc:
        _record_denied(
            request,
            session,
            current_human,
            approval_id=approval_id,
            reason_code="approval_decision_not_allowed",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "approval_decision_not_allowed",
                "message": "This Human role cannot decide approval requests",
            },
        ) from exc
    except HumanConfirmationInvalidError as exc:
        _record_denied(
            request,
            session,
            current_human,
            approval_id=approval_id,
            reason_code="human_confirmation_invalid",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "human_confirmation_invalid",
                "message": "The Human confirmation is invalid, expired, or already used",
            },
        ) from exc
    except ApprovalInvalidStateError as exc:
        _record_denied(
            request,
            session,
            current_human,
            approval_id=approval_id,
            reason_code="approval_invalid_state",
        )
        raise _invalid_state(str(exc)) from exc
    except (ApprovalInvalidIdempotencyKeyError, ApprovalIdempotencyConflictError) as exc:
        _record_denied(
            request,
            session,
            current_human,
            approval_id=approval_id,
            reason_code=(
                "invalid_idempotency_key"
                if isinstance(exc, ApprovalInvalidIdempotencyKeyError)
                else "idempotency_conflict"
            ),
        )
        raise _idempotency_error(exc) from exc

    if result.replayed:
        response.headers["Idempotency-Replayed"] = "true"
    return get_human_approval_request(
        session,
        user=current_human,
        approval_id=result.approval.approval_id,
    )
