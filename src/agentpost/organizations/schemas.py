from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from agentpost.accounts.schemas import EmailChallengeStart
from agentpost.control.schemas import OrganizationMembershipResponse, OrganizationResponse


class OrganizationGovernanceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OrganizationCreateResponse(OrganizationGovernanceModel):
    organization: OrganizationResponse
    membership: OrganizationMembershipResponse


class OrganizationInvitationCreate(OrganizationGovernanceModel):
    email: str = Field(min_length=3, max_length=320)
    role: Literal["admin", "member", "auditor"] = "member"
    expires_in_seconds: int = Field(default=72 * 60 * 60, ge=60 * 60, le=7 * 24 * 60 * 60)

    @field_validator("email")
    @classmethod
    def canonical_email(cls, value: str) -> str:
        return EmailChallengeStart.canonical_email(value)


class OrganizationInvitationResponse(OrganizationGovernanceModel):
    invitation_id: UUID
    organization_id: UUID
    email: str
    role: Literal["admin", "member", "auditor"]
    status: Literal["pending", "accepted", "revoked", "expired"]
    token_prefix: str
    expires_at: datetime
    created_at: datetime


class OrganizationInvitationCreated(OrganizationGovernanceModel):
    invitation: OrganizationInvitationResponse
    verification_uri: str
    test_acceptance_token: str | None = None


class OrganizationInvitationAccept(OrganizationGovernanceModel):
    token: str = Field(min_length=30, max_length=160)


class OrganizationInvitationAccepted(OrganizationGovernanceModel):
    organization: OrganizationResponse
    membership: OrganizationMembershipResponse


class OrganizationMembershipUpdate(OrganizationGovernanceModel):
    role: Literal["owner", "admin", "member", "auditor"]
