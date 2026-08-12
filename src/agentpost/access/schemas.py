from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agentpost.identity.addressing import canonicalize_agent_address

InboundPolicy = Literal["public", "allowlist", "contacts_only", "private"]
RuleEffect = Literal["allow", "block"]
RuleSubjectType = Literal["agent", "domain"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def canonicalize_domain(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("domain must be a string")
    canonical = value.strip().lower()
    if len(canonical) > 255:
        raise ValueError("domain must contain at most 255 characters")
    try:
        return canonicalize_agent_address(f"a@{canonical}").partition("@")[2]
    except ValueError as exc:
        raise ValueError("domain must be a valid ASCII DNS-style domain") from exc


class AccessPolicyUpdate(StrictModel):
    inbound_policy: InboundPolicy


class AccessRuleCreate(StrictModel):
    effect: RuleEffect
    subject_type: RuleSubjectType
    subject: str = Field(min_length=1, max_length=320)

    @model_validator(mode="after")
    def canonical_subject(self) -> AccessRuleCreate:
        if self.subject_type == "agent":
            self.subject = canonicalize_agent_address(self.subject)
        else:
            self.subject = canonicalize_domain(self.subject)
        return self


class AccessRuleResponse(StrictModel):
    id: UUID
    agent_id: UUID
    effect: RuleEffect
    subject_type: RuleSubjectType
    subject: str
    created_at: datetime


class AccessPolicyResponse(StrictModel):
    agent_id: UUID
    inbound_policy: InboundPolicy
    rules: list[AccessRuleResponse]
