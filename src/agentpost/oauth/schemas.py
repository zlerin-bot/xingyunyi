from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OAuthModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DeviceAuthorizationResponse(OAuthModel):
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_in: int
    interval: int


class OAuthTokenResponse(OAuthModel):
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int
    refresh_token: str
    scope: str
    resource: str


class OAuthTokenInfo(OAuthModel):
    active: Literal[True] = True
    client_id: str
    scope: str
    resource: str
    sub: UUID
    connector_id: str
    exp: int


class OAuthClientRegistrationRequest(OAuthModel):
    client_name: str
    redirect_uris: list[str]
    grant_types: list[str] = Field(default_factory=lambda: ["authorization_code", "refresh_token"])
    response_types: list[str] = Field(default_factory=lambda: ["code"])
    token_endpoint_auth_method: Literal["none"] = "none"
    application_type: Literal["native", "web"] | None = None
    scope: str | None = None


class OAuthClientRegistrationResponse(OAuthModel):
    client_id: str
    client_id_issued_at: int
    client_secret_expires_at: Literal[0] = 0
    client_name: str
    redirect_uris: list[str]
    grant_types: list[str]
    response_types: list[str]
    token_endpoint_auth_method: Literal["none"] = "none"
