from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

from agentpost.identity.addressing import canonicalize_agent_address

MAX_CONTENT_BYTES = 1024 * 1024
MAX_METADATA_BYTES = 64 * 1024
MAX_JSON_DEPTH = 16


class MessageType(StrEnum):
    message = "message"
    task = "task"
    result = "result"
    request = "request"
    response = "response"
    notification = "notification"
    event = "event"
    error = "error"
    system = "system"


class Priority(StrEnum):
    low = "low"
    normal = "normal"
    high = "high"
    urgent = "urgent"


class InboxStatus(StrEnum):
    unread = "unread"
    delivered = "delivered"
    read = "read"
    acked = "acked"


def _aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must include a timezone offset")
    return value.astimezone(UTC)


AwareDatetime = Annotated[datetime, AfterValidator(_aware_datetime)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


def _json_depth(value: Any, depth: int = 0) -> int:
    if depth > MAX_JSON_DEPTH:
        return depth
    if isinstance(value, dict):
        return max((_json_depth(item, depth + 1) for item in value.values()), default=depth)
    if isinstance(value, list):
        return max((_json_depth(item, depth + 1) for item in value), default=depth)
    return depth


def _validate_json_limits(value: JsonValue, *, max_bytes: int, label: str) -> JsonValue:
    if _json_depth(value) > MAX_JSON_DEPTH:
        raise ValueError(f"{label} exceeds maximum nesting depth")
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > max_bytes:
        raise ValueError(f"{label} exceeds maximum encoded size")
    return value


class RecipientCreate(StrictModel):
    address: str = Field(min_length=3, max_length=320)

    @field_validator("address")
    @classmethod
    def canonical_address(cls, value: str) -> str:
        return canonicalize_agent_address(value)


class ContentCreate(StrictModel):
    format: Literal["text", "markdown", "json"] = "text"
    body: JsonValue

    @model_validator(mode="after")
    def validate_body(self) -> ContentCreate:
        if self.format in {"text", "markdown"} and not isinstance(self.body, str):
            raise ValueError("text and markdown content bodies must be strings")
        _validate_json_limits(self.body, max_bytes=MAX_CONTENT_BYTES, label="content body")
        return self


class TaskPayload(StrictModel):
    instruction: str = Field(min_length=1, max_length=MAX_CONTENT_BYTES)
    deadline: AwareDatetime | None = None
    expected_output: str | None = Field(default=None, max_length=1000)


class ResultPayload(StrictModel):
    status: Literal["completed", "partial", "failed", "cancelled"]
    summary: str | None = Field(default=None, max_length=10_000)


class MessageCreate(StrictModel):
    to: list[RecipientCreate] = Field(min_length=1, max_length=1)
    message_type: MessageType = Field(alias="type")
    subject: str = Field(max_length=500)
    content: ContentCreate
    task: TaskPayload | None = None
    attachments: list[UUID] = Field(default_factory=list, max_length=32)
    priority: Priority = Priority.normal
    requires_ack: bool = True
    metadata: dict[str, JsonValue] = Field(default_factory=dict, max_length=64)
    expires_at: AwareDatetime | None = None

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        _validate_json_limits(value, max_bytes=MAX_METADATA_BYTES, label="metadata")
        return value

    @field_validator("attachments")
    @classmethod
    def attachments_are_not_enabled_yet(cls, value: list[UUID]) -> list[UUID]:
        if value:
            raise ValueError("attachments are introduced in protocol milestone 6")
        return value

    @model_validator(mode="after")
    def validate_message_semantics(self) -> MessageCreate:
        if self.message_type == MessageType.task and self.task is None:
            raise ValueError("task messages require a task payload")
        if self.message_type != MessageType.task and self.task is not None:
            raise ValueError("task payload is only valid for task messages")
        if self.message_type == MessageType.result:
            raise ValueError("result messages must be created as replies")
        if self.expires_at is not None and self.expires_at <= datetime.now(UTC):
            raise ValueError("expires_at must be in the future")
        return self


class AgentReference(StrictModel):
    agent_id: UUID
    address: str


class ContentResponse(StrictModel):
    format: Literal["text", "markdown", "json"]
    body: JsonValue
    security_label: Literal["external_agent_content"] = "external_agent_content"


class DeliveryResponse(StrictModel):
    delivery_id: UUID
    recipient_agent_id: UUID
    inbox_seq: int
    status: str
    delivery_attempts: int
    delivered_at: datetime | None
    read_at: datetime | None
    acked_at: datetime | None
    error: str | None


class MessageResponse(StrictModel):
    spec_version: Literal["0.1"] = "0.1"
    message_id: str
    sender: AgentReference = Field(alias="from")
    to: list[AgentReference]
    message_type: MessageType = Field(alias="type")
    subject: str
    content: ContentResponse
    task: TaskPayload | None = None
    result: ResultPayload | None = None
    attachments: list[dict[str, JsonValue]] = Field(default_factory=list)
    thread_id: UUID
    reply_to: str | None
    priority: Priority
    requires_ack: bool
    metadata: dict[str, JsonValue]
    created_at: datetime
    accepted_at: datetime
    expires_at: datetime | None
    delivery: DeliveryResponse


class InboxResponse(StrictModel):
    items: list[MessageResponse]
    next_cursor: str | None
    has_more: bool
