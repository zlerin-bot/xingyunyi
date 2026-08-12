"""Environment-only configuration for the stdio MCP adapter."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from typing import Literal, cast

from agentpost_sdk import ConfigurationError

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


@dataclass(frozen=True, slots=True)
class Settings:
    server: str
    api_key: str = field(repr=False)
    timeout_seconds: float
    log_level: LogLevel

    @classmethod
    def from_env(cls) -> Settings:
        api_key = os.environ.get("AGENTPOST_API_KEY", "").strip()
        if not api_key:
            raise ConfigurationError("AGENTPOST_API_KEY is required")

        server = os.environ.get("AGENTPOST_SERVER", "http://127.0.0.1:8000").strip()
        if not server:
            raise ConfigurationError("AGENTPOST_SERVER must not be empty")

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
