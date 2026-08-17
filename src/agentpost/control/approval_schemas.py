from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator


class ApprovalModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


MAX_APPROVAL_PAYLOAD_BYTES = 64 * 1024
MAX_APPROVAL_JSON_DEPTH = 16

ApprovalRisk = Literal["low", "medium", "high", "critical"]
ApprovalStatus = Literal["pending", "approved", "rejected", "cancelled", "expired"]
ApprovalDecisionValue = Literal["approved", "rejected"]


def _json_depth(value: JsonValue, depth: int = 0) -> int:
    if depth > MAX_APPROVAL_JSON_DEPTH:
        return depth
    if isinstance(value, dict):
        return max((_json_depth(item, depth + 1) for item in value.values()), default=depth)
    if isinstance(value, list):
        return max((_json_depth(item, depth + 1) for item in value), default=depth)
    return depth


class ApprovalRequestCreate(ApprovalModel):
    action_type: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z][a-z0-9_.-]{0,63}$",
    )
    summary: str = Field(min_length=1, max_length=300)
    justification: str | None = Field(default=None, max_length=2000)
    risk_level: ApprovalRisk = "medium"
    payload: dict[str, JsonValue] = Field(default_factory=dict, max_length=64)
    expires_at: datetime | None = None

    @field_validator("action_type", "summary")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned

    @field_validator("justification")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("payload")
    @classmethod
    def validate_payload(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        if _json_depth(value) > MAX_APPROVAL_JSON_DEPTH:
            raise ValueError("payload exceeds maximum nesting depth")
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(encoded) > MAX_APPROVAL_PAYLOAD_BYTES:
            raise ValueError("payload exceeds maximum encoded size")
        return value

    @field_validator("expires_at")
    @classmethod
    def future_aware_expiration(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("expires_at must include a timezone offset")
        normalized = value.astimezone(UTC)
        now = datetime.now(UTC)
        if normalized <= now:
            raise ValueError("expires_at must be in the future")
        if normalized > now + timedelta(days=7):
            raise ValueError("expires_at must be within seven days")
        return normalized


class ApprovalDecisionCreate(ApprovalModel):
    decision: ApprovalDecisionValue
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("note")
    @classmethod
    def clean_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class ApprovalConfirmationCreate(ApprovalModel):
    intent: Literal["approve", "reject"]


class ApprovalConfirmationResponse(ApprovalModel):
    confirmation_token: str
    intent: Literal["approve", "reject"]
    approval_id: str
    expires_at: datetime


class ApprovalRequestResponse(ApprovalModel):
    approval_id: str
    requester_agent_id: UUID
    requester_address: str
    action_type: str
    summary: str
    justification: str | None
    risk_level: ApprovalRisk
    payload: dict[str, JsonValue]
    status: ApprovalStatus
    expires_at: datetime
    created_at: datetime
    updated_at: datetime
    decided_at: datetime | None
    decision_note: str | None = None
    security_label: Literal["external_agent_content"] = "external_agent_content"
    execution_effect: Literal["none"] = "none"


class ApprovalRequestListResponse(ApprovalModel):
    items: list[ApprovalRequestResponse]


class OrbitApprovalRequest(ApprovalModel):
    approval_id: str
    requester_agent_id: UUID
    requester_address: str
    action_type: str
    summary: str | None
    justification: str | None
    risk_level: ApprovalRisk
    payload: dict[str, JsonValue]
    status: ApprovalStatus
    access_role: Literal["owner", "operator", "viewer", "auditor"]
    can_decide: bool
    content_redacted: bool
    expires_at: datetime
    created_at: datetime
    updated_at: datetime
    decided_at: datetime | None
    decision_note: str | None = None
    security_label: Literal["external_agent_content"] = "external_agent_content"
    execution_effect: Literal["none"] = "none"


class OrbitApprovalListResponse(ApprovalModel):
    items: list[OrbitApprovalRequest]

    @model_validator(mode="after")
    def ensure_redacted_items_have_no_external_content(self) -> OrbitApprovalListResponse:
        for item in self.items:
            if item.content_redacted and (
                item.summary is not None or item.justification is not None or item.payload
            ):
                raise ValueError("redacted approval items must omit external content")
        return self
