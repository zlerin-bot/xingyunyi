from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    SecretStr,
    field_validator,
    model_validator,
)

from agentpost.accounts.schemas import EmailChallengeStart
from agentpost.accounts.usernames import canonicalize_human_username
from agentpost.control.schemas import OrganizationMembershipResponse, OrganizationResponse
from agentpost.messaging.schemas import (
    ContentCreate,
    MessageType,
    Priority,
    ResultPayload,
    TaskPayload,
    validate_message_metadata,
)


class OrganizationGovernanceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OrganizationCreateResponse(OrganizationGovernanceModel):
    organization: OrganizationResponse
    membership: OrganizationMembershipResponse


class OrganizationInvitationCreate(OrganizationGovernanceModel):
    username: str | None = Field(default=None, min_length=3, max_length=32)
    email: str | None = Field(default=None, min_length=3, max_length=320)
    role: Literal["admin", "member", "auditor"] = "member"
    expires_in_seconds: int = Field(default=72 * 60 * 60, ge=60 * 60, le=7 * 24 * 60 * 60)

    @field_validator("username")
    @classmethod
    def canonical_username(cls, value: str | None) -> str | None:
        return canonicalize_human_username(value) if value is not None else None

    @field_validator("email")
    @classmethod
    def canonical_email(cls, value: str | None) -> str | None:
        return EmailChallengeStart.canonical_email(value) if value is not None else None

    @model_validator(mode="after")
    def one_invitee_identifier(self) -> OrganizationInvitationCreate:
        if (self.username is None) == (self.email is None):
            raise ValueError("supply exactly one of username or email")
        return self


class OrganizationInvitationResponse(OrganizationGovernanceModel):
    invitation_id: UUID
    organization_id: UUID
    email: str | None
    username: str | None = None
    role: Literal["admin", "member", "auditor"]
    status: Literal["pending", "accepted", "revoked", "expired"]
    token_prefix: str
    expires_at: datetime
    created_at: datetime


class OrganizationInvitationCreated(OrganizationGovernanceModel):
    invitation: OrganizationInvitationResponse
    verification_uri: str | None = None
    test_acceptance_token: str | None = None


class OrganizationInvitationAccept(OrganizationGovernanceModel):
    token: str = Field(min_length=30, max_length=160)


class OrganizationInvitationPreview(OrganizationGovernanceModel):
    organization_id: UUID
    organization_slug: str
    organization_name: str
    organization_description: str | None
    role: Literal["admin", "member", "auditor"]
    expires_at: datetime


class OrganizationInvitationAccepted(OrganizationGovernanceModel):
    organization: OrganizationResponse
    membership: OrganizationMembershipResponse


class OrganizationInvitationInboxItem(OrganizationGovernanceModel):
    invitation_id: UUID
    organization_id: UUID
    organization_slug: str
    organization_name: str
    organization_description: str | None
    role: Literal["admin", "member", "auditor"]
    expires_at: datetime


class OrganizationMembershipUpdate(OrganizationGovernanceModel):
    role: Literal["owner", "admin", "member", "auditor"]


class OrganizationAgentConfirmationCreate(OrganizationGovernanceModel):
    intent: Literal["assign", "remove"]
    password: SecretStr


class OrganizationAgentConfirmationResponse(OrganizationGovernanceModel):
    confirmation_token: str
    intent: Literal["assign", "remove"]
    organization_id: UUID
    agent_id: UUID
    expires_at: datetime


class OrganizationChannelMessageCreate(OrganizationGovernanceModel):
    message_type: MessageType = Field(default=MessageType.message, alias="type")
    subject: str = Field(default="", max_length=500)
    content: ContentCreate
    task: TaskPayload | None = None
    result: ResultPayload | None = None
    priority: Priority = Priority.normal
    requires_ack: bool = True
    metadata: dict[str, JsonValue] = Field(default_factory=dict, max_length=64)
    thread_id: UUID | None = None
    reply_to_event_id: UUID | None = None
    requested_responder_agent_ids: list[UUID] = Field(default_factory=list, max_length=32)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        return validate_message_metadata(value)

    @field_validator("requested_responder_agent_ids")
    @classmethod
    def responders_are_unique(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("requested responder Agent IDs must be unique")
        return value

    @model_validator(mode="after")
    def validate_message_semantics(self) -> OrganizationChannelMessageCreate:
        if self.message_type == MessageType.task and self.task is None:
            raise ValueError("task messages require a task payload")
        if self.message_type != MessageType.task and self.task is not None:
            raise ValueError("task payload is only valid for task messages")
        if self.message_type == MessageType.result and self.result is None:
            raise ValueError("result messages require a result payload")
        if self.message_type != MessageType.result and self.result is not None:
            raise ValueError("result payload is only valid for result messages")
        if (self.thread_id is None) != (self.reply_to_event_id is None):
            raise ValueError("thread_id and reply_to_event_id must be supplied together")
        return self


class OrganizationChannelMessageResponse(OrganizationGovernanceModel):
    event_id: UUID
    organization_id: UUID
    organization_slug: str
    thread_id: UUID
    reply_to_event_id: UUID | None
    sender_agent_id: UUID
    recipient_agent_ids: list[UUID]
    requested_responder_agent_ids: list[UUID]
    reply_policy: Literal["addressed_agents_reply"] = "addressed_agents_reply"
    message_ids: list[str]
    created_at: datetime
    replayed: bool = False


class OrganizationChannelAgent(OrganizationGovernanceModel):
    agent_id: UUID
    address: str
    handle: str | None
    display_name: str


class OrganizationChannelSummary(OrganizationGovernanceModel):
    organization_id: UUID
    organization_slug: str
    organization_name: str
    agents: list[OrganizationChannelAgent]


class OrganizationDomainCreate(OrganizationGovernanceModel):
    domain: str = Field(min_length=3, max_length=253)

    @field_validator("domain")
    @classmethod
    def canonical_domain(cls, value: str) -> str:
        domain = value.strip().lower().rstrip(".")
        labels = domain.split(".")
        if len(labels) < 2 or any(
            not label
            or len(label) > 63
            or not label[0].isalnum()
            or not label[-1].isalnum()
            or any(
                not (character.isascii() and (character.isalnum() or character == "-"))
                for character in label
            )
            for label in labels
        ):
            raise ValueError("domain must be a canonical ASCII DNS name")
        return domain


class OrganizationDomainResponse(OrganizationGovernanceModel):
    domain_id: UUID
    organization_id: UUID
    domain: str
    status: Literal["pending", "verified", "revoked"]
    verification_record_name: str
    verification_prefix: str
    created_at: datetime
    last_checked_at: datetime | None
    verified_at: datetime | None


class OrganizationDomainCreated(OrganizationGovernanceModel):
    domain: OrganizationDomainResponse
    verification_record_type: Literal["TXT"] = "TXT"
    verification_value: str
