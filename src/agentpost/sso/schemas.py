from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from agentpost.accounts.schemas import EmailChallengeStart, PasswordMfaProof


class OidcModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OidcProviderCreate(OidcModel):
    display_name: str = Field(min_length=1, max_length=100)
    issuer: str = Field(min_length=8, max_length=1000)
    client_id: str = Field(min_length=1, max_length=255)
    client_secret: SecretStr = Field(min_length=12, max_length=2000)

    @field_validator("display_name", "issuer", "client_id")
    @classmethod
    def strip_nonempty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned.rstrip("/") if "://" in cleaned else cleaned


class OidcProviderResponse(OidcModel):
    provider_id: UUID
    organization_id: UUID
    display_name: str
    issuer: str
    client_id: str
    status: Literal["active", "disabled"]
    created_at: datetime
    updated_at: datetime


class OidcProviderDiscoveryRequest(OidcModel):
    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def canonical_email(cls, value: str) -> str:
        return EmailChallengeStart.canonical_email(value)


class OidcLoginStartResponse(OidcModel):
    authorization_url: str
    expires_at: datetime


class OidcLinkStart(PasswordMfaProof):
    pass


class OidcCallbackQuery(OidcModel):
    code: str = Field(min_length=1, max_length=4000)
    state: str = Field(min_length=20, max_length=512)
