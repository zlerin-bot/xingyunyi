from __future__ import annotations

import logging
import re
import time
from uuid import uuid4

from fastapi import Request, Response

logger = logging.getLogger("agentpost.http")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


async def request_context_middleware(request: Request, call_next) -> Response:
    supplied = request.headers.get("X-Request-ID", "")
    request_id = supplied if _REQUEST_ID.fullmatch(supplied) else str(uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()
    status_code = 500

    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception as exc:
        # Exception messages can contain database parameters or other external
        # values. Keep the operational signal without serializing the exception,
        # traceback, request body, or headers into the standard HTTP log stream.
        logger.error(
            "request.failed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "exception_type": type(exc).__name__,
                "message_id": None,
                "agent_id": None,
                "thread_id": None,
            },
        )
        raise
    finally:
        duration_ms = round((time.perf_counter() - started) * 1000, 3)
        logger.info(
            "request.completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "message_id": getattr(request.state, "message_id", None),
                "agent_id": getattr(request.state, "agent_id", None),
                "thread_id": getattr(request.state, "thread_id", None),
            },
        )

    response.headers["X-Request-ID"] = request_id
    return response
