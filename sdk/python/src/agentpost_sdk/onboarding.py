from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from agentpost_sdk.errors import ConfigurationError, ProtocolError, TransportError

if TYPE_CHECKING:
    from agentpost_sdk.client import AgentPost


class PairingInstructions(BaseModel):
    """Short-lived Human-facing pairing information; never contains the device secret."""

    model_config = ConfigDict(extra="ignore")

    pairing_id: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_at: datetime
    interval: int = Field(ge=1, le=60)


class ConnectorAgent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    address: str
    handle: str | None = None
    display_name: str


class ConnectorState(BaseModel):
    model_config = ConfigDict(extra="ignore")

    connector_id: str
    connector_type: str
    display_name: str
    status: Literal["active", "replaced", "revoked"]
    health_status: Literal["unknown", "healthy", "degraded", "error"]
    last_heartbeat_at: datetime | None = None
    last_error_code: str | None = None
    credential_rotated_at: datetime | None = None


class ConnectorHeartbeat(BaseModel):
    model_config = ConfigDict(extra="ignore")

    connector: ConnectorState
    agent: ConnectorAgent
    current: bool
    server_time: datetime
    recommended_interval_seconds: int = Field(ge=10, le=300)


class ConnectorCredentialRotation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    connector_id: str
    agent: ConnectorAgent
    api_key: SecretStr
    rotated_at: datetime


class PairingSession:
    """A zero-credential Connector pairing operation."""

    _server: str
    _device_code: str
    _http: httpx.Client
    _transport: httpx.BaseTransport | None
    _request_timeout: float | httpx.Timeout
    _next_poll_seconds: int

    def __init__(
        self,
        *,
        server: str,
        instructions: PairingInstructions,
        device_code: str,
        request_timeout: float | httpx.Timeout,
        transport: httpx.BaseTransport | None,
    ) -> None:
        self.instructions = instructions
        self._server = server
        self._device_code = device_code
        self._request_timeout = request_timeout
        self._transport = transport
        self._next_poll_seconds = instructions.interval
        self._http = httpx.Client(
            base_url=f"{server}/api/v1",
            headers={"User-Agent": "agentpost-python/0.1.0"},
            timeout=request_timeout,
            transport=transport,
            follow_redirects=False,
        )

    instructions: PairingInstructions

    def __repr__(self) -> str:
        return (
            f"PairingSession(server={self._server!r}, pairing_id={self.instructions.pairing_id!r})"
        )

    def __enter__(self) -> PairingSession:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def poll(self) -> AgentPost | None:
        """Poll once. None means Human authorization is still pending."""

        from agentpost_sdk.client import AgentPost

        try:
            response = self._http.post(
                "/connect/pairings/token",
                json={"device_code": self._device_code},
            )
        except httpx.HTTPError as exc:
            raise TransportError("AgentPost pairing poll did not complete") from exc
        retry_after = response.headers.get("Retry-After")
        if retry_after and retry_after.isdigit():
            self._next_poll_seconds = max(1, min(60, int(retry_after)))
        if response.is_error:
            AgentPost._raise_api_error(response)
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProtocolError(
                "AgentPost returned a non-JSON pairing response",
                status_code=response.status_code,
                code="MALFORMED_RESPONSE",
                request_id=response.headers.get("X-Request-ID"),
            ) from exc
        if response.status_code == 202 or payload.get("status") == "pending":
            return None
        api_key = payload.get("api_key")
        if payload.get("status") != "approved" or not isinstance(api_key, str):
            raise ProtocolError(
                "AgentPost returned an incomplete pairing approval",
                status_code=response.status_code,
                code="MALFORMED_RESPONSE",
                request_id=response.headers.get("X-Request-ID"),
            )
        self.close()
        client = AgentPost(
            self._server,
            api_key,
            timeout=self._request_timeout,
            transport=self._transport,
        )
        connector = payload.get("connector")
        agent = payload.get("agent")
        if isinstance(connector, dict):
            client._connector_id = str(connector.get("connector_id") or "") or None
        if isinstance(agent, dict):
            client._agent_address = str(agent.get("address") or "") or None
        return client

    def wait(
        self,
        *,
        timeout: float = 15 * 60,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> AgentPost:
        if timeout <= 0:
            raise ConfigurationError("pairing timeout must be positive")
        deadline = time.monotonic() + timeout
        while True:
            connected = self.poll()
            if connected is not None:
                return connected
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TransportError("AgentPost pairing authorization timed out")
            sleeper(min(float(self._next_poll_seconds), remaining))


def begin_pairing(
    *,
    server: str,
    connector_type: str,
    display_name: str,
    device_name: str | None,
    client_version: str | None,
    capabilities: list[str] | None,
    timeout: float | httpx.Timeout,
    transport: httpx.BaseTransport | None,
) -> PairingSession:
    from agentpost_sdk.client import AgentPost

    public_http = httpx.Client(
        base_url=f"{server}/api/v1",
        headers={"User-Agent": "agentpost-python/0.1.0"},
        timeout=timeout,
        transport=transport,
        follow_redirects=False,
    )
    try:
        try:
            response = public_http.post(
                "/connect/pairings",
                json={
                    "connector_type": connector_type,
                    "display_name": display_name,
                    "device_name": device_name,
                    "client_version": client_version,
                    "capabilities": capabilities or [],
                },
            )
        except httpx.HTTPError as exc:
            raise TransportError("AgentPost pairing request did not complete") from exc
        if response.is_error:
            AgentPost._raise_api_error(response)
        try:
            payload: dict[str, Any] = response.json()
            if not isinstance(payload, dict):
                raise ValueError("pairing response must be an object")
            instructions = PairingInstructions.model_validate(payload)
            device_code = payload["device_code"]
            if not isinstance(device_code, str) or not device_code.startswith("dvc_"):
                raise ValueError("invalid device code")
        except (ValueError, KeyError, ValidationError) as exc:
            raise ProtocolError(
                "AgentPost returned a malformed pairing response",
                status_code=response.status_code,
                code="MALFORMED_RESPONSE",
                request_id=response.headers.get("X-Request-ID"),
            ) from exc
    finally:
        public_http.close()
    return PairingSession(
        server=server,
        instructions=instructions,
        device_code=device_code,
        request_timeout=timeout,
        transport=transport,
    )
