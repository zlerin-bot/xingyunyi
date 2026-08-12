from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from agentpost.attachments.models import Attachment
from agentpost.attachments.schemas import AttachmentResponse
from agentpost.identity.models import Agent
from agentpost.messaging.models import Delivery, Message


class AttachmentNotFoundError(Exception):
    pass


class AttachmentUnavailableError(Exception):
    pass


def attachment_response(attachment: Attachment) -> AttachmentResponse:
    return AttachmentResponse(
        id=attachment.id,
        filename=attachment.filename,
        content_type=attachment.content_type,
        size=attachment.size,
        sha256=attachment.sha256,
        state=attachment.state,
        created_at=attachment.created_at,
    )


def visible_attachment(session: Session, *, agent_id: UUID, attachment_id: UUID) -> Attachment:
    attachment = session.get(Attachment, attachment_id)
    if attachment is None:
        raise AttachmentNotFoundError(attachment_id)
    if attachment.state == "pending":
        if attachment.uploader_agent_id != agent_id:
            raise AttachmentNotFoundError(attachment_id)
        return attachment
    allowed = session.scalar(
        select(Message.id)
        .join(Delivery, Delivery.message_id == Message.id)
        .where(
            Message.id == attachment.message_id,
            or_(Message.sender_agent_id == agent_id, Delivery.recipient_agent_id == agent_id),
        )
    )
    if allowed is None:
        raise AttachmentNotFoundError(attachment_id)
    return attachment


def bind_attachments(
    session: Session,
    *,
    sender: Agent,
    attachment_ids: list[UUID],
    message_id: str,
) -> None:
    if not attachment_ids:
        return
    if len(set(attachment_ids)) != len(attachment_ids):
        raise AttachmentUnavailableError("attachment IDs must not be repeated")
    for attachment_id in attachment_ids:
        result = session.execute(
            update(Attachment)
            .where(
                Attachment.id == attachment_id,
                Attachment.uploader_agent_id == sender.id,
                Attachment.state == "pending",
                Attachment.message_id.is_(None),
            )
            .values(state="attached", message_id=message_id)
        )
        if result.rowcount != 1:
            raise AttachmentUnavailableError("attachment is not available for this sender")


def attachment_metadata(attachment: Attachment) -> dict[str, str | int]:
    return {
        "id": str(attachment.id),
        "filename": attachment.filename,
        "content_type": attachment.content_type,
        "size": attachment.size,
        "sha256": attachment.sha256,
    }
