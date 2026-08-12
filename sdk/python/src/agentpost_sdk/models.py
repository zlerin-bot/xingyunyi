from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

if TYPE_CHECKING:
    from agentpost_sdk.client import AgentPost


class APIModel(BaseModel):
    """Forward-compatible response model for an independently versioned server."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class AgentReference(APIModel):
    agent_id: UUID
    address: str


class Content(APIModel):
    format: str
    body: Any
    security_label: str = "external_agent_content"


class Delivery(APIModel):
    delivery_id: UUID
    recipient_agent_id: UUID
    inbox_seq: int
    status: str
    delivery_attempts: int
    delivered_at: datetime | None = None
    read_at: datetime | None = None
    acked_at: datetime | None = None
    error: str | None = None


class Attachment(APIModel):
    id: UUID
    filename: str
    content_type: str
    size: int
    sha256: str
    state: str | None = None
    created_at: datetime | None = None


class Message(APIModel):
    spec_version: str = "0.1"
    message_id: str
    sender: AgentReference = Field(alias="from")
    to: list[AgentReference]
    message_type: str = Field(alias="type")
    subject: str
    content: Content
    task: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    attachments: list[Attachment] = Field(default_factory=list)
    thread_id: UUID
    reply_to: str | None = None
    priority: str
    requires_ack: bool
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    accepted_at: datetime
    expires_at: datetime | None = None
    delivery: Delivery
    idempotency_replayed: bool = False

    _client: AgentPost | None = PrivateAttr(default=None)

    def _bind(self, client: AgentPost) -> Message:
        self._client = client
        return self

    def _require_client(self) -> AgentPost:
        if self._client is None:
            raise RuntimeError("message is not bound to an AgentPost client")
        return self._client

    def mark_read(self) -> Message:
        return self._require_client().messages.read(self.message_id)

    def read(self) -> Message:
        return self.mark_read()

    def ack(self) -> Message:
        return self._require_client().messages.ack(self.message_id)

    def reply(self, body: Any, **kwargs: Any) -> Message:
        return self._require_client().messages.reply(self.message_id, body=body, **kwargs)


class InboxPage(APIModel):
    items: list[Message]
    next_cursor: str | None = None
    has_more: bool = False


class AgentProfile(APIModel):
    id: UUID
    address: str
    display_name: str
    description: str | None = None
    domain: str
    status: str
    public_key: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    endpoint: str | None = None
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime | None = None
    capability_verification: str | None = None


class DirectoryPage(APIModel):
    items: list[AgentProfile]


class DownloadedFile(APIModel):
    path: Path
    size: int
    sha256: str


DownloadedAttachment = DownloadedFile
