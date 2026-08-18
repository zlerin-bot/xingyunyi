"""OAuth-protected Streamable HTTP MCP server."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Literal, cast
from urllib.parse import urlsplit

import httpx
from agentpost_sdk import AgentPost, ConfigurationError
from mcp.server import MCPServer
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings

from agentpost_mcp import __version__
from agentpost_mcp.server import INSTRUCTIONS
from agentpost_mcp.tools import register_tools

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
REMOTE_SCOPE = "agentpost.messaging"


def _origin(value: str, name: str) -> str:
    cleaned = value.strip().rstrip("/")
    parsed = urlsplit(cleaned)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ConfigurationError(f"{name} must be an HTTP(S) origin")
    return cleaned


def _resource_url(value: str) -> str:
    cleaned = value.strip().rstrip("/")
    parsed = urlsplit(cleaned)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path != "/mcp"
    ):
        raise ConfigurationError("AGENTPOST_MCP_RESOURCE_URL must end with /mcp")
    return cleaned


def _csv(value: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item.strip() for item in value.split(",") if item.strip()))


@dataclass(frozen=True, slots=True)
class RemoteSettings:
    server: str
    issuer_url: str
    resource_url: str
    host: str
    port: int
    timeout_seconds: float
    log_level: LogLevel
    allowed_hosts: tuple[str, ...]
    allowed_origins: tuple[str, ...]

    @classmethod
    def from_env(cls) -> RemoteSettings:
        server = _origin(
            os.environ.get("AGENTPOST_SERVER", "http://127.0.0.1:8000"),
            "AGENTPOST_SERVER",
        )
        issuer = _origin(
            os.environ.get("AGENTPOST_OAUTH_ISSUER", server),
            "AGENTPOST_OAUTH_ISSUER",
        )
        resource = _resource_url(os.environ.get("AGENTPOST_MCP_RESOURCE_URL", f"{issuer}/mcp"))
        host = os.environ.get("AGENTPOST_MCP_HOST", "127.0.0.1").strip()
        if not host or any(character.isspace() for character in host):
            raise ConfigurationError("AGENTPOST_MCP_HOST is invalid")
        try:
            port = int(os.environ.get("AGENTPOST_MCP_PORT", "8001"))
        except ValueError as exc:
            raise ConfigurationError("AGENTPOST_MCP_PORT must be an integer") from exc
        if not 1 <= port <= 65535:
            raise ConfigurationError("AGENTPOST_MCP_PORT must be between 1 and 65535")
        try:
            timeout = float(os.environ.get("AGENTPOST_TIMEOUT_SECONDS", "30"))
        except ValueError as exc:
            raise ConfigurationError("AGENTPOST_TIMEOUT_SECONDS must be a number") from exc
        if not math.isfinite(timeout) or not 0 < timeout <= 300:
            raise ConfigurationError(
                "AGENTPOST_TIMEOUT_SECONDS must be finite and between 0 and 300"
            )
        log_level = os.environ.get("AGENTPOST_MCP_LOG_LEVEL", "WARNING").strip().upper()
        if log_level not in _LOG_LEVELS:
            raise ConfigurationError("AGENTPOST_MCP_LOG_LEVEL is invalid")
        resource_parts = urlsplit(resource)
        default_host = resource_parts.netloc
        default_origin = f"{resource_parts.scheme}://{resource_parts.netloc}"
        allowed_hosts = _csv(os.environ.get("AGENTPOST_MCP_ALLOWED_HOSTS", default_host))
        allowed_origins = _csv(os.environ.get("AGENTPOST_MCP_ALLOWED_ORIGINS", default_origin))
        if not allowed_hosts or not allowed_origins:
            raise ConfigurationError("Remote MCP host and origin allowlists must not be empty")
        return cls(
            server=server,
            issuer_url=issuer,
            resource_url=resource,
            host=host,
            port=port,
            timeout_seconds=timeout,
            log_level=cast(LogLevel, log_level),
            allowed_hosts=allowed_hosts,
            allowed_origins=allowed_origins,
        )


class AgentPostTokenVerifier(TokenVerifier):
    """Validate opaque OAuth tokens through the cloud AgentPost API."""

    def __init__(
        self,
        settings: RemoteSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.transport = transport

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            async with httpx.AsyncClient(
                base_url=self.settings.server,
                timeout=self.settings.timeout_seconds,
                transport=self.transport,
                follow_redirects=False,
            ) as client:
                response = await client.get(
                    "/api/v1/oauth/token-info",
                    headers={"Authorization": f"Bearer {token}"},
                )
            if response.status_code != 200:
                return None
            payload = response.json()
            if (
                payload.get("active") is not True
                or payload.get("resource") != self.settings.resource_url
                or REMOTE_SCOPE not in str(payload.get("scope", "")).split()
                or not isinstance(payload.get("client_id"), str)
                or not isinstance(payload.get("sub"), str)
                or not isinstance(payload.get("exp"), int)
            ):
                return None
            return AccessToken(
                token=token,
                client_id=payload["client_id"],
                scopes=str(payload["scope"]).split(),
                expires_at=payload["exp"],
                resource=payload["resource"],
                subject=payload["sub"],
                claims={"iss": self.settings.issuer_url},
            )
        except (httpx.HTTPError, ValueError, TypeError):
            return None


def remote_client_factory(
    settings: RemoteSettings,
    *,
    transport: httpx.BaseTransport | None = None,
):
    def create() -> AgentPost:
        access = get_access_token()
        if access is None or access.resource != settings.resource_url:
            raise ConfigurationError("A valid Remote MCP OAuth token is required")
        if REMOTE_SCOPE not in access.scopes:
            raise ConfigurationError("The Remote MCP OAuth token lacks messaging scope")
        return AgentPost(
            settings.server,
            access.token,
            timeout=settings.timeout_seconds,
            transport=transport,
        )

    return create


def create_remote_server(
    settings: RemoteSettings,
    *,
    token_verifier: TokenVerifier | None = None,
    client_transport: httpx.BaseTransport | None = None,
) -> MCPServer[None]:
    server: MCPServer[None] = MCPServer(
        name="agentpost-remote",
        title="星云驿 · 云驿 Remote MCP",
        description="OAuth-protected persistent asynchronous Agent messaging",
        instructions=INSTRUCTIONS,
        version=__version__,
        log_level=settings.log_level,
        token_verifier=token_verifier or AgentPostTokenVerifier(settings),
        auth=AuthSettings(
            issuer_url=settings.issuer_url,
            resource_server_url=settings.resource_url,
            required_scopes=[REMOTE_SCOPE],
        ),
    )
    register_tools(
        server,
        remote_client_factory(settings, transport=client_transport),
    )
    return server
