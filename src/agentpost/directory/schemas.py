from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from agentpost.identity.schemas import AgentProfile, StrictModel


class DirectoryAgentProfile(AgentProfile):
    """A safe public profile returned as an unverified discovery candidate."""

    capability_verification: Literal["self_declared"] = "self_declared"


class DirectorySearchResponse(StrictModel):
    items: list[DirectoryAgentProfile]


class RecipientResolveRequest(StrictModel):
    query: str = Field(min_length=1, max_length=200)

    @field_validator("query")
    @classmethod
    def clean_query(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("query must not be blank")
        if any(ord(character) < 32 or ord(character) == 127 for character in cleaned):
            raise ValueError("query must not contain control characters")
        return cleaned


class RecipientCandidate(StrictModel):
    agent_id: UUID
    address: str
    handle: str | None
    display_name: str
    owner_display_name: str | None = None
    agent_type: str | None = None
    organization_name: str | None = None
    label: str
    match_kind: Literal[
        "address",
        "handle",
        "display_name",
        "human_agent",
        "fuzzy",
    ]
    security_label: Literal["external_agent_content"] = "external_agent_content"


class RecipientResolution(StrictModel):
    status: Literal["resolved", "needs_clarification", "not_found"]
    query: str
    match: RecipientCandidate | None = None
    candidates: list[RecipientCandidate] = Field(default_factory=list, max_length=5)
    total_candidates: int = Field(default=0, ge=0)
    reason: Literal[
        "unique_match",
        "recipient_ambiguous",
        "recipient_not_found",
    ]
    security_label: Literal["external_agent_content"] = "external_agent_content"
