from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from agentpost.control.schemas import HumanProfile

_EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$",
    flags=re.ASCII,
)


class AccountModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmailChallengeStart(AccountModel):
    email: str = Field(min_length=3, max_length=320)
    purpose: Literal["register", "recover"]

    @field_validator("email")
    @classmethod
    def canonical_email(cls, value: str) -> str:
        canonical = value.strip().lower()
        if not _EMAIL_PATTERN.fullmatch(canonical):
            raise ValueError("email must be a canonical ASCII email address")
        return canonical


class EmailChallengeResponse(AccountModel):
    challenge_id: str
    expires_at: datetime
    retry_after: int
    delivery: Literal["email"] = "email"
    test_verification_code: str | None = None


class RegistrationComplete(AccountModel):
    challenge_id: str = Field(min_length=10, max_length=64)
    code: str = Field(pattern=r"^[0-9]{8}$")
    display_name: str = Field(min_length=1, max_length=200)
    password: SecretStr

    @field_validator("display_name")
    @classmethod
    def clean_display_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("display_name must not be blank")
        return cleaned


class HumanLogin(AccountModel):
    email: str = Field(min_length=3, max_length=320)
    password: SecretStr
    totp_code: str | None = Field(default=None, pattern=r"^[0-9]{6}$")
    recovery_code: str | None = Field(default=None, min_length=8, max_length=32)

    @field_validator("email")
    @classmethod
    def canonical_email(cls, value: str) -> str:
        return EmailChallengeStart.canonical_email(value)


class RecoveryComplete(AccountModel):
    challenge_id: str = Field(min_length=10, max_length=64)
    code: str = Field(pattern=r"^[0-9]{8}$")
    new_password: SecretStr
    totp_code: str | None = Field(default=None, pattern=r"^[0-9]{6}$")
    recovery_code: str | None = Field(default=None, min_length=8, max_length=32)


class BrowserAuthenticationResponse(AccountModel):
    user: HumanProfile
    csrf_token: str
    expires_at: datetime
    auth_method: str
    mfa_authenticated: bool


class PasswordMfaProof(AccountModel):
    password: SecretStr
    totp_code: str | None = Field(default=None, pattern=r"^[0-9]{6}$")
    recovery_code: str | None = Field(default=None, min_length=8, max_length=32)


class TotpSetupStart(PasswordMfaProof):
    pass


class TotpSetupResponse(AccountModel):
    secret: str
    provisioning_uri: str


class TotpSetupConfirm(AccountModel):
    code: str = Field(pattern=r"^[0-9]{6}$")


class TotpEnabledResponse(AccountModel):
    enabled: Literal[True] = True
    recovery_codes: list[str]


class HumanKeyRotate(PasswordMfaProof):
    label: str = Field(default="self-service", min_length=1, max_length=100)

    @field_validator("label")
    @classmethod
    def clean_label(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("label must not be blank")
        return cleaned


class HumanKeyRotationResponse(AccountModel):
    access_key: str
    key_prefix: str
    label: str
    created_at: datetime


class SecurityOverview(AccountModel):
    email_verified: bool
    password_configured: bool
    mfa_enabled: bool
    active_human_keys: int


class ConnectorReleaseInfo(AccountModel):
    version: str
    wheel_url: str
    wheel_sha256: str


class HumanAuthConfig(AccountModel):
    self_service_enabled: bool
    open_registration_enabled: bool
    enterprise_oidc_enabled: bool = False
    codex_setup_platforms: list[str] = Field(default_factory=list)
    connector_release: ConnectorReleaseInfo
    managed_agent_domain: str
    password_min_length: int = 12
    mfa_supported: bool = True
