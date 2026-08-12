from __future__ import annotations

from fastapi.testclient import TestClient


def test_validation_errors_use_protocol_error_envelope(client: TestClient) -> None:
    response = client.post(
        "/api/v1/agents",
        json={"address": "alice@agents.local", "sender_agent_id": "forged"},
        headers={"X-Request-ID": "validation-envelope-test"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "SCHEMA_VALIDATION_FAILED",
            "message": "The request does not match the required schema",
            "request_id": "validation-envelope-test",
            "details": [
                {
                    "type": "extra_forbidden",
                    "loc": ["body", "sender_agent_id"],
                    "message": "Extra inputs are not permitted",
                }
            ],
        }
    }


def test_http_errors_use_protocol_error_envelope(client: TestClient) -> None:
    response = client.get(
        "/api/v1/agents/2e78d3be-fc9a-4cb3-89ef-404b8768d3bd",
        headers={"X-Request-ID": "not-found-envelope-test"},
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "AGENT_NOT_FOUND",
            "message": "Agent was not found",
            "request_id": "not-found-envelope-test",
            "details": {},
        }
    }
