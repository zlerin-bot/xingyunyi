from __future__ import annotations

import json
import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agentpost.api.middleware import request_context_middleware


def test_unhandled_exception_log_omits_exception_message_and_traceback(caplog) -> None:
    sentinel = "EXCEPTION_SECRET_SENTINEL_4c1d"
    app = FastAPI()
    app.middleware("http")(request_context_middleware)

    @app.get("/explode")
    def explode() -> None:
        raise RuntimeError(sentinel)

    caplog.set_level(logging.INFO, logger="agentpost.http")
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/explode")

    assert response.status_code == 500
    serialized = json.dumps(
        [
            {
                "message": record.getMessage(),
                "attributes": record.__dict__,
            }
            for record in caplog.records
            if record.name == "agentpost.http"
        ],
        default=str,
        sort_keys=True,
    )
    assert "request.failed" in serialized
    assert "RuntimeError" in serialized
    assert sentinel not in serialized
    assert "Traceback" not in serialized
