from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response, status

from agentpost.api.dependencies import CurrentAgentDep, SessionDep, SettingsDep
from agentpost.identity.addressing import canonicalize_agent_address
from agentpost.messaging.cursors import InvalidCursorError
from agentpost.messaging.schemas import (
    AwareDatetime,
    InboxResponse,
    InboxStatus,
    MessageCreate,
    MessageResponse,
    MessageType,
    Priority,
)
from agentpost.messaging.service import (
    IdempotencyConflictError,
    InboxFilters,
    InvalidIdempotencyKeyError,
    MessageNotFoundError,
    RecipientNotFoundError,
    get_visible_message,
    list_inbox,
    message_response,
    send_message,
)

router = APIRouter(prefix="/api/v1", tags=["messages"])


@router.post(
    "/messages",
    response_model=MessageResponse,
    response_model_by_alias=True,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def create_message(
    request: Request,
    response: Response,
    payload: MessageCreate,
    session: SessionDep,
    current_agent: CurrentAgentDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> MessageResponse:
    try:
        result = send_message(
            session,
            sender=current_agent,
            payload=payload,
            idempotency_key=idempotency_key,
            request_id=request.state.request_id,
        )
    except InvalidIdempotencyKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_idempotency_key", "message": str(exc)},
        ) from exc
    except IdempotencyConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "idempotency_conflict",
                "message": "The idempotency key was already used for a different request",
            },
        ) from exc
    except RecipientNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "recipient_not_found", "message": "Recipient was not found"},
        ) from exc

    request.state.message_id = result.message.id
    request.state.thread_id = str(result.message.thread_id)
    if result.replayed:
        response.status_code = status.HTTP_200_OK
        response.headers["Idempotency-Replayed"] = "true"
    return message_response(result.message)


@router.get(
    "/inbox",
    response_model=InboxResponse,
    response_model_by_alias=True,
    response_model_exclude_none=True,
)
def read_inbox(
    session: SessionDep,
    settings: SettingsDep,
    current_agent: CurrentAgentDep,
    inbox_status: Annotated[InboxStatus | None, Query(alias="status")] = None,
    sender: str | None = None,
    message_type: Annotated[MessageType | None, Query(alias="type")] = None,
    priority: Priority | None = None,
    since: AwareDatetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(max_length=2048)] = None,
) -> InboxResponse:
    canonical_sender = None
    if sender is not None:
        try:
            canonical_sender = canonicalize_agent_address(sender)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "invalid_agent_address", "message": str(exc)},
            ) from exc
    try:
        return list_inbox(
            session,
            recipient=current_agent,
            filters=InboxFilters(
                status=inbox_status,
                sender=canonical_sender,
                message_type=message_type,
                priority=priority,
                since=since,
            ),
            limit=limit,
            cursor_token=cursor,
            cursor_secret=settings.cursor_secret,
        )
    except InvalidCursorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_cursor", "message": str(exc)},
        ) from exc


@router.get(
    "/messages/{message_id}",
    response_model=MessageResponse,
    response_model_by_alias=True,
    response_model_exclude_none=True,
)
def read_message(
    message_id: str,
    session: SessionDep,
    current_agent: CurrentAgentDep,
) -> MessageResponse:
    try:
        message = get_visible_message(session, agent_id=current_agent.id, message_id=message_id)
    except MessageNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "message_not_found", "message": "Message was not found"},
        ) from exc
    return message_response(message)
