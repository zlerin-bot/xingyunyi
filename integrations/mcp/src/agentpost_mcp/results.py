"""Stable, secret-free MCP result and error projection."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from agentpost_sdk import ConfigurationError, ProtocolError, ResponseError, TransportError
from mcp.types import CallToolResult, TextContent
from pydantic import BaseModel

logger = logging.getLogger(__name__)
_ERROR_CODE = re.compile(r"^[A-Z0-9_]{1,64}$")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_SECRET_SHAPED_REQUEST_ID = re.compile(
    r"^(?:agt|api[-_]?key|authorization|bearer|credential|password|secret|token)[._:-]",
    re.IGNORECASE,
)
_SENSITIVE_KEYS = frozenset(
    {
        "apikey",
        "authorization",
        "credential",
        "credentials",
        "filesystempath",
        "localpath",
        "password",
        "privatekey",
        "secret",
        "storagekey",
        "storagepath",
        "token",
    }
)
_EXTERNAL_PAYLOAD_KEYS = frozenset({"body", "metadata", "result", "task"})


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _jsonable(value.model_dump(mode="json", by_alias=True, exclude_none=True))
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): (
                _jsonable_external(item)
                if _normalized_key(str(key)) in _EXTERNAL_PAYLOAD_KEYS
                else _jsonable(item)
            )
            for key, item in value.items()
            if _normalized_key(str(key)) not in _SENSITIVE_KEYS
        }
    return value


def _jsonable_external(value: Any) -> Any:
    """Preserve opaque business payloads; the enclosing result stays explicitly untrusted."""
    if isinstance(value, BaseModel):
        return _jsonable_external(value.model_dump(mode="json", by_alias=True, exclude_none=True))
    if isinstance(value, list):
        return [_jsonable_external(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable_external(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable_external(item) for key, item in value.items()}
    return value


def success(data: Any, *, external: bool = False) -> CallToolResult:
    payload: dict[str, Any] = {"ok": True, "data": _jsonable(data)}
    if external:
        payload["security_label"] = "external_agent_content"
    return _result(payload, is_error=False)


def failure(exc: Exception, *, operation: str) -> CallToolResult:
    if isinstance(exc, ConfigurationError):
        error = _error("INVALID_ARGUMENT", "Invalid AgentPost tool argument")
    elif isinstance(exc, ProtocolError):
        ambiguity = _acceptance_ambiguity(exc, operation=operation)
        error = _error(
            "AGENTPOST_PROTOCOL_ERROR",
            "AgentPost returned a malformed response",
            status_code=exc.status_code,
            request_id=_safe_request_id(exc.request_id),
            retryable=bool(ambiguity),
            **ambiguity,
        )
    elif isinstance(exc, ResponseError):
        ambiguity = _acceptance_ambiguity(exc, operation=operation)
        error = _error(
            exc.code if _ERROR_CODE.fullmatch(exc.code or "") else "AGENTPOST_RESPONSE_ERROR",
            "AgentPost request failed",
            status_code=exc.status_code,
            request_id=_safe_request_id(exc.request_id),
            retryable=_retryable_status(exc.status_code),
            **ambiguity,
        )
    elif isinstance(exc, TransportError):
        extra: dict[str, Any] = {}
        if operation in {"send", "reply"}:
            extra["acceptance_unknown"] = True
            if exc.idempotency_key:
                extra["idempotency_key"] = exc.idempotency_key
        error = _error(
            "AGENTPOST_TRANSPORT_ERROR",
            "AgentPost request did not complete",
            retryable=True,
            **extra,
        )
    else:
        logger.error("Unexpected AgentPost MCP tool failure type=%s", type(exc).__name__)
        error = _error("INTERNAL_ERROR", "AgentPost MCP adapter failed")
    return _result({"ok": False, "error": error}, is_error=True)


def _error(
    code: str,
    message: str,
    *,
    status_code: int | None = None,
    request_id: str | None = None,
    retryable: bool = False,
    **extra: Any,
) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message, "retryable": retryable}
    if status_code is not None:
        error["status_code"] = status_code
    if request_id is not None:
        error["request_id"] = request_id
    error.update(extra)
    return error


def _normalized_key(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _safe_request_id(value: str | None) -> str | None:
    if not value or not _REQUEST_ID.fullmatch(value) or _SECRET_SHAPED_REQUEST_ID.match(value):
        return None
    return value


def _retryable_status(status_code: int | None) -> bool:
    return status_code in {408, 429} or (status_code is not None and 500 <= status_code <= 599)


def _acceptance_ambiguity(exc: ResponseError, *, operation: str) -> dict[str, Any]:
    if operation not in {"send", "reply"}:
        return {}
    if not isinstance(exc, ProtocolError) and not _retryable_status(exc.status_code):
        return {}
    extra: dict[str, Any] = {"acceptance_unknown": True}
    if exc.idempotency_key:
        extra["idempotency_key"] = exc.idempotency_key
    return extra


def _result(payload: dict[str, Any], *, is_error: bool) -> CallToolResult:
    rendered = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return CallToolResult(
        content=[TextContent(type="text", text=rendered)],
        structuredContent=payload,
        isError=is_error,
    )
