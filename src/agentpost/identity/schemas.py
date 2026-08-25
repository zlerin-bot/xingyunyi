from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from agentpost.identity.addressing import canonicalize_agent_address
from agentpost.identity.handles import canonicalize_agent_handle


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _normalize_capabilities(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    if len(values) > 128:
        raise ValueError("at most 128 capabilities may be registered")
    for value in values:
        if not isinstance(value, str):
            raise ValueError("each capability must be a string")
        capability = value.strip().lower()
        if not capability or len(capability) > 100:
            raise ValueError("capabilities must contain between 1 and 100 characters")
        if capability not in seen:
            normalized.append(capability)
            seen.add(capability)
    return normalized


class AgentCreate(StrictModel):
    address: str = Field(min_length=3, max_length=320)
    handle: str | None = None
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    capabilities: list[str] = Field(default_factory=list)
    endpoint: str | None = Field(default=None, max_length=2048)
    public_key: str | None = Field(default=None, max_length=16_384)

    @field_validator("address")
    @classmethod
    def canonical_address(cls, value: str) -> str:
        return canonicalize_agent_address(value)

    @field_validator("handle")
    @classmethod
    def canonical_handle(cls, value: str | None) -> str | None:
        return canonicalize_agent_handle(value) if value is not None else None

    @field_validator("display_name")
    @classmethod
    def clean_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("display_name must not be blank")
        return value

    @field_validator("capabilities")
    @classmethod
    def canonical_capabilities(cls, value: list[str]) -> list[str]:
        return _normalize_capabilities(value)


class AgentUpdate(StrictModel):
    handle: str | None = None
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    capabilities: list[str] | None = None
    endpoint: str | None = Field(default=None, max_length=2048)

    @field_validator("handle")
    @classmethod
    def canonical_handle(cls, value: str | None) -> str | None:
        return canonicalize_agent_handle(value) if value is not None else None

    @field_validator("display_name")
    @classmethod
    def clean_display_name(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("display_name cannot be null")
        value = value.strip()
        if not value:
            raise ValueError("display_name must not be blank")
        return value

    @field_validator("capabilities")
    @classmethod
    def canonical_capabilities(cls, value: list[str] | None) -> list[str]:
        if value is None:
            raise ValueError("capabilities cannot be null")
        return _normalize_capabilities(value)


class AgentProfile(StrictModel):
    id: UUID
    address: str
    handle: str | None
    display_name: str
    description: str | None
    domain: str
    status: str
    public_key: str | None
    capabilities: list[str]
    endpoint: str | None
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime | None


class AgentRegistrationResponse(StrictModel):
    agent: AgentProfile
    api_key: str
    api_key_prefix: str
