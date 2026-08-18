from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


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
