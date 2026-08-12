from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated, BinaryIO
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse

from agentpost.api.dependencies import CurrentAgentDep, SessionDep, SettingsDep
from agentpost.attachments.models import Attachment
from agentpost.attachments.schemas import AttachmentResponse
from agentpost.attachments.service import (
    AttachmentNotFoundError,
    attachment_response,
    visible_attachment,
)
from agentpost.identity.models import utc_now
from agentpost.messaging.models import AuditLog
from agentpost.storage import (
    InvalidFilenameError,
    LocalAttachmentStorage,
    StorageObjectNotFoundError,
    UploadTooLargeError,
    validate_filename,
)

router = APIRouter(prefix="/api/v1/attachments", tags=["attachments"])


def _stream_and_close(source: BinaryIO) -> Iterator[bytes]:
    try:
        while chunk := source.read(LocalAttachmentStorage.chunk_size):
            yield chunk
    finally:
        source.close()


@router.post("", response_model=AttachmentResponse, status_code=status.HTTP_201_CREATED)
def upload_attachment(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    current_agent: CurrentAgentDep,
    file: Annotated[UploadFile, File()],
) -> AttachmentResponse:
    try:
        filename = validate_filename(file.filename or "")
    except InvalidFilenameError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_filename", "message": str(exc)},
        ) from exc
    content_type = (file.content_type or "application/octet-stream")[:255]
    storage = LocalAttachmentStorage(settings.storage_path)
    try:
        stored = storage.store(file.file, max_bytes=settings.max_attachment_bytes)
    except UploadTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail={"code": "attachment_too_large", "message": str(exc)},
        ) from exc

    attachment = Attachment(
        uploader_agent_id=current_agent.id,
        filename=filename,
        content_type=content_type,
        size=stored.size,
        storage_key=stored.storage_key,
        sha256=stored.sha256,
        state="pending",
        created_at=utc_now(),
    )
    session.add(attachment)
    try:
        session.flush()
        session.add(
            AuditLog(
                actor_agent_id=current_agent.id,
                action="attachment.uploaded",
                target_type="attachment",
                target_id=str(attachment.id),
                outcome="success",
                request_id=request.state.request_id,
                audit_metadata={"size": stored.size, "content_type": content_type},
            )
        )
        session.commit()
    except Exception:
        session.rollback()
        storage.delete(stored.storage_key)
        raise
    session.refresh(attachment)
    return attachment_response(attachment)


@router.get("/{attachment_id}")
def download_attachment(
    attachment_id: UUID,
    session: SessionDep,
    settings: SettingsDep,
    current_agent: CurrentAgentDep,
) -> StreamingResponse:
    try:
        attachment = visible_attachment(
            session, agent_id=current_agent.id, attachment_id=attachment_id
        )
        source = LocalAttachmentStorage(settings.storage_path).open(attachment.storage_key)
    except (AttachmentNotFoundError, StorageObjectNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "attachment_not_found", "message": "Attachment was not found"},
        ) from exc
    fallback = "attachment.bin"
    disposition = f"attachment; filename={fallback}; filename*=UTF-8''{quote(attachment.filename)}"
    return StreamingResponse(
        _stream_and_close(source),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": disposition,
            "X-Content-Type-Options": "nosniff",
            "Content-Length": str(attachment.size),
        },
    )
