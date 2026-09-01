from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProjectModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectCreate(ProjectModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    due_at: datetime | None = None

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("title cannot be blank")
        return cleaned

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("due_at")
    @classmethod
    def normalize_due_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("due_at must include a timezone")
        return value.astimezone(UTC)


class ProjectMembersInvite(ProjectModel):
    human_user_ids: list[UUID] = Field(min_length=1, max_length=50)

    @field_validator("human_user_ids")
    @classmethod
    def unique_human_ids(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("human_user_ids must be unique")
        return value


class ProjectStatusUpdate(ProjectModel):
    status: Literal["active", "archived"]


class FriendAgent(ProjectModel):
    agent_id: UUID
    display_name: str
    address: str
    capabilities: list[str]
    last_contact_at: datetime


class FriendResponse(ProjectModel):
    human_user_id: UUID
    username: str
    display_name: str
    last_contact_at: datetime
    capabilities: list[str]
    agents: list[FriendAgent]


class ProjectMember(ProjectModel):
    human_user_id: UUID
    username: str
    display_name: str
    role: Literal["owner", "member"]
    status: Literal["invited", "active"]
    agent: FriendAgent | None = None
    invited_at: datetime
    joined_at: datetime | None


class ProjectActivityResponse(ProjectModel):
    activity_id: str
    kind: Literal[
        "created",
        "member_invited",
        "member_joined",
        "member_declined",
        "archived",
        "restored",
        "agent_delivery",
        "agent_update",
    ]
    actor_human_user_id: UUID | None
    actor_display_name: str | None
    target_human_user_id: UUID | None
    target_display_name: str | None
    agent_id: UUID | None = None
    agent_display_name: str | None = None
    subject: str | None = None
    delivery_status: str | None = None
    security_label: Literal["platform_event", "external_agent_content"]
    created_at: datetime


class ProjectSummary(ProjectModel):
    project_id: UUID
    title: str
    description: str | None
    status: Literal["active", "archived"]
    due_at: datetime | None
    owner_human_user_id: UUID
    owner_display_name: str
    membership_role: Literal["owner", "member"]
    membership_status: Literal["invited", "active"]
    active_member_count: int
    invited_member_count: int
    member_human_user_ids: list[UUID]
    created_at: datetime
    updated_at: datetime


class ProjectDetail(ProjectSummary):
    members: list[ProjectMember]
    activities: list[ProjectActivityResponse]
