from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def error_payload(
    request: Request,
    *,
    code: str,
    message: str,
    details: Any = None,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code.upper(),
            "message": message,
            "request_id": _request_id(request),
            "details": {} if details is None else details,
        }
    }


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict):
        code = str(detail.get("code", "INVALID_REQUEST"))
        message = str(detail.get("message", "The request could not be completed"))
        details = detail.get("details", {})
    else:
        code = "INVALID_REQUEST"
        message = str(detail)
        details = {}
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(
            request,
            code=code,
            message=message,
            details=details,
        ),
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details: list[dict[str, Any]] = []
    for error in exc.errors():
        safe_error = {
            "type": error.get("type"),
            "loc": list(error.get("loc", ())),
            "message": error.get("msg"),
        }
        details.append(safe_error)
    return JSONResponse(
        status_code=422,
        content=error_payload(
            request,
            code="SCHEMA_VALIDATION_FAILED",
            message="The request does not match the required schema",
            details=details,
        ),
    )
