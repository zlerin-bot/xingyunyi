from __future__ import annotations

from fastapi.testclient import TestClient


def test_public_agent_integration_contract_preserves_machine_and_human_semantics(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/protocol/contract")

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "public, max-age=300"
    assert response.headers["X-AgentPost-Contract-Version"] == "0.1"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    payload = response.json()
    assert payload["contract"] == "AGENTPOST_AGENT_INTEGRATION"
    assert payload["version"] == "0.1"
    assert payload["openapi_url"] == "/openapi.json"
    send_endpoint = next(
        endpoint for endpoint in payload["endpoints"] if endpoint["path"] == "/api/v1/messages"
    )
    assert send_endpoint["bearer_auth_required"] is True
    assert send_endpoint["required_headers"] == ["Idempotency-Key"]
    assert payload["content"]["native_formats"] == ["text", "markdown", "json"]
    assert payload["content"]["html_is_native_body_format"] is False
    assert payload["content"]["max_attachments"] == 32
    assert payload["states"]["ack_means_received_not_completed"] is True
    assert payload["states"]["direct_reply_handles_task_round"] is True
    assert payload["states"]["structured_result_takes_precedence"] is True
    assert payload["heartbeat"]["recommended_interval_seconds"] == 30
    assert payload["heartbeat"]["offline_after_seconds"] == 90
    assert payload["heartbeat"]["online_requires_current_healthy_heartbeat"] is True
    assert payload["synchronization"]["source_of_truth"] == "persistent_inbox"
    assert payload["synchronization"]["recommended_mode"] == "poll_with_cursor"
    assert payload["synchronization"]["recommended_poll_interval_seconds"] == 30
    assert payload["synchronization"]["push_wakeup_available"] is False
    assert payload["synchronization"]["human_view_changes_agent_delivery_state"] is False
    assert payload["interoperability"] == {
        "core_protocol": "agentpost_http_v1",
        "mcp": "adapter",
        "a2a": "mapping_design_only",
        "a2a_runtime_endpoint": None,
        "smtp_imap": False,
    }
    assert payload["human_presentation"]["default_view"] == "readable_summary"
    assert payload["human_presentation"]["raw_agent_data"] == "available_collapsed"
    assert payload["human_presentation"]["security_label"] == "external_agent_content"
    assert payload["human_presentation"]["independent_state_axes"] == [
        "human_view",
        "delivery",
        "agent_read",
        "ack",
        "task_result",
    ]


def test_agent_integration_contract_is_in_openapi(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/api/v1/protocol/contract" in response.json()["paths"]
