from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response, status

from agentpost.access.service import DeliveryNotAllowedError
from agentpost.api.dependencies import CurrentAgentDep, SessionDep, SettingsDep
from agentpost.attachments.service import AttachmentUnavailableError
from agentpost.identity.addressing import canonicalize_agent_address
from agentpost.messaging.cursors import InvalidCursorError
from agentpost.messaging.schemas import (
    AwareDatetime,
    InboxResponse,
    InboxStatus,
    MessageCreate,
    MessageReply,
    MessageResponse,
    MessageType,
    Priority,
    ThreadListResponse,
    ThreadResponse,
)
from agentpost.messaging.service import (
    IdempotencyConflictError,
    InboxFilters,
    InvalidIdempotencyKeyError,
    InvalidStateTransitionError,
    MessageNotFoundError,
    RecipientNotFoundError,
    get_thread,
    get_visible_message,
    list_inbox,
    list_threads,
    message_response,
    reply_to_message,
    send_message,
    transition_delivery,
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
    except DeliveryNotAllowedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "delivery_not_allowed",
                "message": "The recipient does not accept this delivery",
            },
        ) from exc
    except AttachmentUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "attachment_unavailable", "message": str(exc)},
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


def _transition_message(
    *,
    transition: str,
    request: Request,
    message_id: str,
    session: SessionDep,
    current_agent: CurrentAgentDep,
) -> MessageResponse:
    try:
        message = transition_delivery(
            session,
            recipient=current_agent,
            message_id=message_id,
            transition=transition,
            request_id=request.state.request_id,
        )
    except MessageNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "message_not_found", "message": "Message was not found"},
        ) from exc
    except InvalidStateTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "invalid_state_transition",
                "message": "The delivery cannot make this state transition",
            },
        ) from exc
    request.state.message_id = message.id
    request.state.thread_id = str(message.thread_id)
    return message_response(message)


@router.post(
    "/messages/{message_id}/read",
    response_model=MessageResponse,
    response_model_by_alias=True,
    response_model_exclude_none=True,
)
def mark_message_read(
    request: Request,
    message_id: str,
    session: SessionDep,
    current_agent: CurrentAgentDep,
) -> MessageResponse:
    return _transition_message(
        transition="read",
        request=request,
        message_id=message_id,
        session=session,
        current_agent=current_agent,
    )


@router.post(
    "/messages/{message_id}/ack",
    response_model=MessageResponse,
    response_model_by_alias=True,
    response_model_exclude_none=True,
)
def acknowledge_message(
    request: Request,
    message_id: str,
    session: SessionDep,
    current_agent: CurrentAgentDep,
) -> MessageResponse:
    return _transition_message(
        transition="ack",
        request=request,
        message_id=message_id,
        session=session,
        current_agent=current_agent,
    )


@router.post(
    "/messages/{message_id}/reply",
    response_model=MessageResponse,
    response_model_by_alias=True,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def reply_message(
    request: Request,
    response: Response,
    message_id: str,
    payload: MessageReply,
    session: SessionDep,
    current_agent: CurrentAgentDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> MessageResponse:
    try:
        result = reply_to_message(
            session,
            sender=current_agent,
            parent_message_id=message_id,
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
    except MessageNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "message_not_found", "message": "Message was not found"},
        ) from exc
    except RecipientNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "recipient_not_found", "message": "Recipient was not found"},
        ) from exc
    except DeliveryNotAllowedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "delivery_not_allowed",
                "message": "The recipient does not accept this delivery",
            },
        ) from exc
    except InvalidStateTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "invalid_state_transition",
                "message": "A result reply requires a task parent message",
            },
        ) from exc
    except AttachmentUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "attachment_unavailable", "message": str(exc)},
        ) from exc
    request.state.message_id = result.message.id
    request.state.thread_id = str(result.message.thread_id)
    if result.replayed:
        response.status_code = status.HTTP_200_OK
        response.headers["Idempotency-Replayed"] = "true"
    return message_response(result.message)


@router.get(
    "/threads",
    response_model=ThreadListResponse,
    response_model_by_alias=True,
    response_model_exclude_none=True,
)
def read_threads(session: SessionDep, current_agent: CurrentAgentDep) -> ThreadListResponse:
    return list_threads(session, agent=current_agent)


@router.get(
    "/threads/{thread_id}",
    response_model=ThreadResponse,
    response_model_by_alias=True,
    response_model_exclude_none=True,
)
def read_thread(
    thread_id: UUID,
    session: SessionDep,
    current_agent: CurrentAgentDep,
) -> ThreadResponse:
    try:
        return get_thread(session, agent=current_agent, thread_id=thread_id)
    except MessageNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "thread_not_found", "message": "Thread was not found"},
        ) from exc
