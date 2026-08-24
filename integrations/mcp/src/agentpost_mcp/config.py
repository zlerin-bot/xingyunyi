"""Environment-only configuration for the stdio MCP adapter."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from typing import Literal, Protocol, cast

from agentpost_sdk import ConfigurationError, ConnectorCredential, KeyringCredentialStore

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


class CredentialStore(Protocol):
    def load(self, *, server: str, profile: str) -> ConnectorCredential | None: ...


def _server_from_env() -> str:
    server = os.environ.get("AGENTPOST_SERVER", "http://127.0.0.1:8000").strip().rstrip("/")
    if not server:
        raise ConfigurationError("AGENTPOST_SERVER must not be empty")
    return server


def _resolve_api_key(*, server: str, credential_store: CredentialStore | None) -> str:
    api_key = os.environ.get("AGENTPOST_API_KEY", "").strip()
    profile = os.environ.get("AGENTPOST_PROFILE", "").strip()
    if api_key and profile:
        raise ConfigurationError("AGENTPOST_API_KEY and AGENTPOST_PROFILE are mutually exclusive")
    if api_key:
        return api_key
    if not profile:
        raise ConfigurationError("AGENTPOST_API_KEY or AGENTPOST_PROFILE is required")
    if len(profile) > 200:
        raise ConfigurationError("AGENTPOST_PROFILE must contain at most 200 characters")

    store = credential_store or KeyringCredentialStore()
    credential = store.load(server=server, profile=profile)
    if credential is None:
        raise ConfigurationError("No OS credential was found for AGENTPOST_PROFILE")
    return credential.api_key


@dataclass(frozen=True, slots=True)
class Settings:
    server: str
    api_key: str = field(repr=False)
    timeout_seconds: float
    log_level: LogLevel

    @classmethod
    def from_env(cls, *, credential_store: CredentialStore | None = None) -> Settings:
        server = _server_from_env()
        api_key = _resolve_api_key(server=server, credential_store=credential_store)

        timeout_raw = os.environ.get("AGENTPOST_TIMEOUT_SECONDS", "30").strip()
        try:
            timeout_seconds = float(timeout_raw)
        except ValueError as exc:
            raise ConfigurationError("AGENTPOST_TIMEOUT_SECONDS must be a number") from exc
        if not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 300:
            raise ConfigurationError(
                "AGENTPOST_TIMEOUT_SECONDS must be finite and between 0 and 300"
            )

        log_level = os.environ.get("AGENTPOST_MCP_LOG_LEVEL", "WARNING").strip().upper()
        if log_level not in _LOG_LEVELS:
            raise ConfigurationError(
                "AGENTPOST_MCP_LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL"
            )
        return cls(
            server=server,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            log_level=cast(LogLevel, log_level),
        )
