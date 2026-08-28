from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, Response, status

from agentpost.api.dependencies import CurrentAgentDep, SessionDep
from agentpost.organizations.channel_service import (
    OrganizationChannelIdempotencyConflictError,
    OrganizationChannelInvalidIdempotencyKeyError,
    OrganizationChannelNotFoundError,
    OrganizationChannelResponderNotFoundError,
    OrganizationChannelThreadNotFoundError,
    get_organization_channel,
    send_organization_channel_message,
)
from agentpost.organizations.schemas import (
    OrganizationChannelMessageCreate,
    OrganizationChannelMessageResponse,
    OrganizationChannelSummary,
)

router = APIRouter(prefix="/api/v1", tags=["organization-channels"])


@router.get(
    "/organization-channel",
    response_model=OrganizationChannelSummary,
)
def read_current_organization_channel(
    session: SessionDep,
    current_agent: CurrentAgentDep,
) -> OrganizationChannelSummary:
    try:
        return get_organization_channel(session, sender=current_agent)
    except OrganizationChannelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "organization_channel_not_found"},
        ) from exc


@router.post(
    "/organizations/{organization_id}/channel/messages",
    response_model=OrganizationChannelMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_organization_channel_message(
    organization_id: UUID,
    payload: OrganizationChannelMessageCreate,
    request: Request,
    response: Response,
    session: SessionDep,
    current_agent: CurrentAgentDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> OrganizationChannelMessageResponse:
    try:
        result = send_organization_channel_message(
            session,
            organization_id=organization_id,
            sender=current_agent,
            payload=payload,
            idempotency_key=idempotency_key,
            request_id=request.state.request_id,
        )
    except OrganizationChannelInvalidIdempotencyKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_idempotency_key"},
        ) from exc
    except OrganizationChannelIdempotencyConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "idempotency_conflict"},
        ) from exc
    except OrganizationChannelResponderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "requested_responder_not_found"},
        ) from exc
    except OrganizationChannelThreadNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "organization_thread_not_found"},
        ) from exc
    except OrganizationChannelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "organization_not_found"},
        ) from exc

    request.state.thread_id = str(result.response.thread_id)
    if result.replayed:
        response.status_code = status.HTTP_200_OK
        response.headers["Idempotency-Replayed"] = "true"
    return result.response
