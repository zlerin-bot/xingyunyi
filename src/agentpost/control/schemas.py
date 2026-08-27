from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from agentpost.accounts.usernames import canonicalize_human_username
from agentpost.control.approval_schemas import OrbitApprovalRequest
from agentpost.identity.handles import canonicalize_agent_handle

_EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$",
    flags=re.ASCII,
)


class ControlModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HumanCreate(ControlModel):
    email: str = Field(min_length=3, max_length=320)
    username: str | None = Field(default=None, min_length=3, max_length=32)
    display_name: str = Field(min_length=1, max_length=200)

    @field_validator("email")
    @classmethod
    def canonical_email(cls, value: str) -> str:
        canonical = value.strip().lower()
        if not _EMAIL_PATTERN.fullmatch(canonical):
            raise ValueError("email must be a canonical ASCII email address")
        return canonical

    @field_validator("display_name")
    @classmethod
    def clean_display_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("display_name must not be blank")
        return cleaned

    @field_validator("username")
    @classmethod
    def canonical_username(cls, value: str | None) -> str | None:
        return canonicalize_human_username(value) if value is not None else None


class HumanProfile(ControlModel):
    id: UUID
    email: str
    username: str
    display_name: str
    status: str
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime | None


class HumanRegistrationResponse(ControlModel):
    user: HumanProfile
    access_key: str
    access_key_prefix: str


class HumanSessionResponse(ControlModel):
    user: HumanProfile
    expires_at: datetime
    csrf_token: str
    authentication: Literal["browser_session"] = "browser_session"


class OrganizationCreate(ControlModel):
    slug: str = Field(min_length=2, max_length=63, pattern=r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("slug", mode="before")
    @classmethod
    def canonical_slug(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("name must not be blank")
        return cleaned

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class OrganizationResponse(ControlModel):
    id: UUID
    slug: str
    name: str
    description: str | None
    status: Literal["active", "archived"]
    member_count: int
    agent_count: int
    created_at: datetime
    updated_at: datetime


class OrganizationMembershipCreate(ControlModel):
    role: Literal["owner", "admin", "member", "auditor"]


class OrganizationMembershipResponse(ControlModel):
    organization_id: UUID
    human_user_id: UUID
    human_email: str
    role: Literal["owner", "admin", "member", "auditor"]
    created_at: datetime
    updated_at: datetime


class OrganizationAgentResponse(ControlModel):
    organization_id: UUID
    agent_id: UUID
    agent_address: str
    assigned_at: datetime


class OrbitOrganization(ControlModel):
    id: UUID
    slug: str
    name: str
    description: str | None
    membership_role: Literal["owner", "admin", "member", "auditor"]
    member_count: int
    agent_count: int


class OrbitOrganizationReference(ControlModel):
    id: UUID
    slug: str
    name: str
    membership_role: Literal["owner", "admin", "member", "auditor"] | None


class AgentAccessCreate(ControlModel):
    role: Literal["owner", "operator", "viewer", "auditor"]


class AgentAccessResponse(ControlModel):
    human_user_id: UUID
    agent_id: UUID
    agent_address: str
    role: Literal["owner", "operator", "viewer", "auditor"]
    granted_at: datetime


class OrbitAgent(ControlModel):
    id: UUID
    address: str
    handle: str | None
    display_name: str
    description: str | None
    status: str
    role: Literal["owner", "operator", "viewer", "auditor"]
    access_source: Literal["direct", "organization"] = "direct"
    organization: OrbitOrganizationReference | None = None
    capabilities: list[str]
    last_seen_at: datetime | None
    connection_state: Literal[
        "connected",
        "awaiting_agent",
        "disconnected",
        "offline",
        "connection_error",
    ]
    current_connector_type: str | None = None
    current_connector_name: str | None = None
    current_connector_device: str | None = None
    current_connector_version: str | None = None
    current_connector_health: str | None = None
    current_connector_last_heartbeat_at: datetime | None = None
    current_connector_error_code: str | None = None
    unread_count: int
    pending_task_count: int


class OrbitAgentHandleUpdate(ControlModel):
    handle: str | None

    @field_validator("handle")
    @classmethod
    def canonical_handle(cls, value: str | None) -> str | None:
        return canonicalize_agent_handle(value) if value is not None else None


class OrbitAgentDelete(ControlModel):
    confirmation: Literal["delete"]


class OrbitMessageAgent(ControlModel):
    id: UUID
    address: str
    handle: str | None
    display_name: str
    agent_type: str | None = None
    owner_display_name: str | None = None
    owned_by_current_human: bool = False


class OrbitMessageAttachment(ControlModel):
    id: UUID
    filename: str
    content_type: str
    size: int


class OrbitMessage(ControlModel):
    message_id: str
    sender: OrbitMessageAgent
    recipient: OrbitMessageAgent
    sender_address: str
    recipient_address: str
    subject: str
    message_type: str
    priority: str
    content_format: str
    content_body: JsonValue | None
    content_redacted: bool = False
    security_label: Literal["external_agent_content"] = "external_agent_content"
    thread_id: UUID
    reply_to: str | None
    requires_ack: bool
    task_instruction: str | None = None
    task_expected_output: str | None = None
    task_deadline: datetime | None = None
    result_summary: str | None = None
    attachments: list[OrbitMessageAttachment] = Field(default_factory=list)
    communication_state: str
    work_state: str | None
    created_at: datetime


class OrbitThreadSummary(ControlModel):
    thread_id: UUID
    topic: str
    participants: list[OrbitMessageAgent]
    organizations: list[OrbitOrganizationReference] = Field(default_factory=list)
    latest_message_id: str
    latest_message_type: str
    latest_message_summary: JsonValue | None
    latest_content_redacted: bool = False
    latest_activity_at: datetime
    message_count: int
    attachment_count: int
    pending_task_count: int
    exception_count: int
    agent_pending_read_count: int
    latest_sender: OrbitMessageAgent
    latest_recipient: OrbitMessageAgent
    conversation_state: Literal[
        "needs_attention",
        "in_progress",
        "completed",
        "waiting_for_me",
        "waiting_for_other",
        "updated",
    ]
    human_view_state: Literal["unread", "viewed"]
    human_viewed_at: datetime | None = None


class OrbitThreadDetail(ControlModel):
    thread_id: UUID
    topic: str
    participants: list[OrbitMessageAgent]
    organizations: list[OrbitOrganizationReference] = Field(default_factory=list)
    messages: list[OrbitMessage]
    human_view_state: Literal["unread", "viewed"]
    human_viewed_at: datetime | None = None


class OrbitThreadViewState(ControlModel):
    thread_id: UUID
    viewed_through_message_id: str
    human_view_state: Literal["viewed"] = "viewed"
    viewed_at: datetime


class OrbitTask(ControlModel):
    task_message_id: str
    subject: str
    requester_address: str
    assignee_address: str
    instruction: str | None
    priority: str
    communication_state: str
    work_state: Literal["pending", "completed", "partial", "failed", "cancelled"]
    result_message_id: str | None
    result_summary: str | None
    created_at: datetime
    updated_at: datetime
    security_label: Literal["external_agent_content"] = "external_agent_content"


class OrbitMetrics(ControlModel):
    agent_count: int
    connected_agent_count: int
    online_recently_count: int
    unread_delivery_count: int
    pending_task_count: int
    failed_task_count: int
    pending_approval_count: int


class OrbitDashboard(ControlModel):
    user: HumanProfile
    metrics: OrbitMetrics
    organizations: list[OrbitOrganization]
    agents: list[OrbitAgent]
    recent_messages: list[OrbitMessage]
    tasks: list[OrbitTask]
    approvals: list[OrbitApprovalRequest]
    plane: Literal["human_control_plane"] = "human_control_plane"
    product: Literal["星云驿"] = "星云驿"
    surface: Literal["星轨"] = "星轨"
    data_plane: Literal["云驿"] = "云驿"
    capabilities: dict[str, Any] = Field(
        default_factory=lambda: {
            "observation": True,
            "agent_actions": False,
            "approvals": True,
        }
    )
