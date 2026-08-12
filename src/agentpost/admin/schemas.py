from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AdminModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AdminAgent(AdminModel):
    id: UUID
    address: str
    display_name: str
    domain: str
    status: str
    inbound_policy: str
    capabilities: list[str]
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime | None


class AdminMessage(AdminModel):
    message_id: str
    sender_agent_id: UUID
    recipient_agent_id: UUID
    message_type: str
    subject: str
    thread_id: UUID
    reply_to: str | None
    priority: str
    created_at: datetime
    accepted_at: datetime
    delivery_status: str


class AdminThread(AdminModel):
    thread_id: UUID
    message_count: int
    last_message_at: datetime


class AdminDelivery(AdminModel):
    delivery_id: UUID
    message_id: str
    recipient_agent_id: UUID
    inbox_seq: int
    status: str
    attempts: int
    delivered_at: datetime | None
    read_at: datetime | None
    acked_at: datetime | None
    error: str | None


class AdminAudit(AdminModel):
    id: UUID
    actor_agent_id: UUID | None
    action: str
    target_type: str
    target_id: str
    outcome: str
    reason_code: str | None
    request_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class AdminList(AdminModel):
    items: list[Any]
