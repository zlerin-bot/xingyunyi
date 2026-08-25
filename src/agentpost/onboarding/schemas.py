from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from agentpost.identity.handles import canonicalize_agent_handle


class OnboardingModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _clean_capabilities(values: list[str]) -> list[str]:
    if len(values) > 64:
        raise ValueError("at most 64 capabilities may be supplied during pairing")
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = value.strip().lower()
        if not cleaned or len(cleaned) > 100:
            raise ValueError("capabilities must contain between 1 and 100 characters")
        if cleaned not in seen:
            result.append(cleaned)
            seen.add(cleaned)
    return result


class PairingCreate(OnboardingModel):
    connector_type: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z][a-z0-9_.-]{0,63}$",
    )
    display_name: str = Field(min_length=1, max_length=200)
    device_name: str | None = Field(default=None, max_length=200)
    client_version: str | None = Field(default=None, max_length=100)
    capabilities: list[str] = Field(default_factory=list)

    @field_validator("connector_type", mode="before")
    @classmethod
    def canonical_connector_type(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("display_name")
    @classmethod
    def clean_display_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("display_name must not be blank")
        return cleaned

    @field_validator("device_name", "client_version")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("capabilities")
    @classmethod
    def canonical_capabilities(cls, value: list[str]) -> list[str]:
        return _clean_capabilities(value)


class PairingCreateResponse(OnboardingModel):
    pairing_id: str
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_at: datetime
    interval: int


class PairingTokenRequest(OnboardingModel):
    device_code: str = Field(min_length=20, max_length=256)


class PairingAgentResponse(OnboardingModel):
    id: UUID
    address: str
    handle: str | None
    display_name: str


class PairingConnectorResponse(OnboardingModel):
    connector_id: str
    connector_type: str
    display_name: str
    device_name: str | None
    client_version: str | None
    status: Literal["active", "replaced", "revoked"]
    health_status: Literal["unknown", "healthy", "degraded", "error"]
    created_at: datetime
    activated_at: datetime
    last_seen_at: datetime | None
    last_heartbeat_at: datetime | None
    last_error_code: str | None
    credential_rotated_at: datetime | None
    revoked_at: datetime | None


class PairingTokenResponse(OnboardingModel):
    status: Literal["pending", "approved"]
    interval: int
    agent: PairingAgentResponse | None = None
    connector: PairingConnectorResponse | None = None
    api_key: str | None = None


class PairingPreview(OnboardingModel):
    pairing_id: str
    user_code_hint: str
    connector_type: str
    connector_display_name: str
    device_name: str | None
    client_version: str | None
    requested_capabilities: list[str]
    status: Literal["pending", "approved", "denied", "expired", "consumed"]
    expires_at: datetime
    agent: PairingAgentResponse | None = None
    security_label: Literal["external_agent_content"] = "external_agent_content"


class PairingConfirmationCreate(OnboardingModel):
    intent: Literal["approve", "deny"]
    user_code: str = Field(min_length=8, max_length=16)
    password: SecretStr | None = None
    totp_code: str | None = Field(default=None, pattern=r"^[0-9]{6}$")
    recovery_code: str | None = Field(default=None, min_length=8, max_length=32)


class PairingConfirmationResponse(OnboardingModel):
    confirmation_token: str
    pairing_id: str
    intent: Literal["approve", "deny"]
    expires_at: datetime


class PairingDecisionCreate(OnboardingModel):
    decision: Literal["approved", "denied"]
    handle: str | None = None
    create_new_agent: bool = False
    local_agent_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?$",
    )
    existing_agent_id: UUID | None = None
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    capabilities: list[str] | None = None

    @field_validator("handle")
    @classmethod
    def canonical_handle(cls, value: str | None) -> str | None:
        return canonicalize_agent_handle(value) if value is not None else None

    @field_validator("local_agent_id", mode="before")
    @classmethod
    def canonical_local_agent_id(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("display_name", "description")
    @classmethod
    def clean_decision_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("capabilities")
    @classmethod
    def canonical_decision_capabilities(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _clean_capabilities(value)

    @model_validator(mode="after")
    def decision_fields_match_action(self) -> PairingDecisionCreate:
        target_count = sum(
            (
                self.create_new_agent,
                self.local_agent_id is not None,
                self.existing_agent_id is not None,
            )
        )
        if self.decision == "approved" and target_count != 1:
            raise ValueError(
                "approved pairing decisions require exactly one of create_new_agent, "
                "local_agent_id, or existing_agent_id"
            )
        if (self.existing_agent_id is not None or self.create_new_agent) and any(
            value is not None
            for value in (
                self.local_agent_id,
                self.display_name,
                self.description,
                self.capabilities,
            )
        ):
            raise ValueError(
                "automatic or existing Agent pairing must not modify Agent profile fields"
            )
        if self.decision == "denied" and (
            self.create_new_agent
            or any(
                value is not None
                for value in (
                    self.handle,
                    self.local_agent_id,
                    self.existing_agent_id,
                    self.display_name,
                    self.description,
                    self.capabilities,
                )
            )
        ):
            raise ValueError("denied pairing decisions must not create or modify an Agent")
        return self


class PairingDecisionResponse(OnboardingModel):
    pairing: PairingPreview
    connector: PairingConnectorResponse | None = None


class OrbitConnector(PairingConnectorResponse):
    agent: PairingAgentResponse
    is_current: bool


class OrbitConnectorList(OnboardingModel):
    items: list[OrbitConnector]


class ConnectorConfirmationResponse(OnboardingModel):
    confirmation_token: str
    connector_id: str
    expires_at: datetime


class ConnectorConfirmationCreate(OnboardingModel):
    password: SecretStr | None = None
    totp_code: str | None = Field(default=None, pattern=r"^[0-9]{6}$")
    recovery_code: str | None = Field(default=None, min_length=8, max_length=32)


class ConnectorHeartbeatCreate(OnboardingModel):
    health_status: Literal["healthy", "degraded", "error"] = "healthy"
    last_error_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        pattern=r"^[A-Z0-9][A-Z0-9_.-]{0,99}$",
    )

    @model_validator(mode="after")
    def error_matches_health(self) -> ConnectorHeartbeatCreate:
        if self.health_status == "healthy" and self.last_error_code is not None:
            raise ValueError("healthy heartbeat must not report an error code")
        if self.health_status == "error" and self.last_error_code is None:
            raise ValueError("error heartbeat requires last_error_code")
        return self


class ConnectorHeartbeatResponse(OnboardingModel):
    connector: PairingConnectorResponse
    agent: PairingAgentResponse
    current: Literal[True] = True
    server_time: datetime
    recommended_interval_seconds: int


class ConnectorCredentialRotationResponse(OnboardingModel):
    connector_id: str
    agent: PairingAgentResponse
    api_key: str
    rotated_at: datetime
