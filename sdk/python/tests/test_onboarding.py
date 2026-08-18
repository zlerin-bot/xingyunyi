from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from agentpost_sdk.onboarding import PairingInstructions, PairingSession

from agentpost import AgentPost


def _pairing_response() -> dict[str, Any]:
    return {
        "pairing_id": "pair_test-session",
        "device_code": "dvc_private-device-secret",
        "user_code": "ABCD-EFGH",
        "verification_uri": "https://agentpost.me/orbit",
        "verification_uri_complete": (
            "https://agentpost.me/orbit?pairing=pair_test-session&code=ABCD-EFGH"
        ),
        "expires_at": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
        "interval": 5,
    }


def test_begin_pairing_exposes_only_short_lived_human_instructions() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(201, json=_pairing_response())

    pairing = AgentPost.begin_pairing(
        "https://agentpost.me",
        connector_type="codex",
        display_name="Codex on Mars MacBook",
        device_name="Mars MacBook",
        client_version="1.0.0",
        capabilities=["financial-research"],
        transport=httpx.MockTransport(handler),
    )

    assert isinstance(pairing, PairingSession)
    assert isinstance(pairing.instructions, PairingInstructions)
    assert pairing.instructions.user_code == "ABCD-EFGH"
    assert "dvc_private-device-secret" not in repr(pairing)
    assert "device_code" not in pairing.instructions.model_dump()
    assert requests[0].url.path == "/api/v1/connect/pairings"
    assert "Authorization" not in requests[0].headers
    body = requests[0].content.decode()
    assert '"connector_type":"codex"' in body
    assert '"capabilities":["financial-research"]' in body
    pairing.close()


def test_connect_waits_for_human_then_returns_authenticated_client_without_key_display() -> None:
    poll_count = 0
    seen_instructions: list[PairingInstructions] = []
    inbox_authorization: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal poll_count
        if request.url.path == "/api/v1/connect/pairings":
            assert "Authorization" not in request.headers
            return httpx.Response(201, json=_pairing_response())
        if request.url.path == "/api/v1/connect/pairings/token":
            assert "Authorization" not in request.headers
            assert "dvc_private-device-secret" in request.content.decode()
            poll_count += 1
            if poll_count == 1:
                return httpx.Response(
                    202,
                    headers={"Retry-After": "1"},
                    json={
                        "status": "pending",
                        "interval": 5,
                        "agent": None,
                        "connector": None,
                        "api_key": None,
                    },
                )
            return httpx.Response(
                200,
                json={
                    "status": "approved",
                    "interval": 5,
                    "agent": {
                        "id": "5a7044c7-6a5e-48e9-90dd-78680c91dcb9",
                        "address": "pluto@agentpost.me",
                        "display_name": "Pluto",
                    },
                    "connector": {
                        "connector_id": "con_test",
                        "connector_type": "codex",
                        "display_name": "Codex",
                        "device_name": "Mars MacBook",
                        "client_version": "1.0.0",
                        "status": "active",
                        "created_at": datetime.now(UTC).isoformat(),
                        "activated_at": datetime.now(UTC).isoformat(),
                        "last_seen_at": None,
                        "revoked_at": None,
                    },
                    "api_key": "agt_connector-private-key",
                },
            )
        if request.url.path == "/api/v1/inbox":
            inbox_authorization.append(request.headers.get("Authorization", ""))
            return httpx.Response(200, json={"items": [], "next_cursor": None, "has_more": False})
        raise AssertionError(request.url)

    client = AgentPost.connect(
        "https://agentpost.me",
        connector_type="codex",
        display_name="Codex",
        open_browser=False,
        on_pairing=seen_instructions.append,
        sleeper=lambda _: None,
        transport=httpx.MockTransport(handler),
    )
    try:
        assert poll_count == 2
        assert [item.user_code for item in seen_instructions] == ["ABCD-EFGH"]
        assert "agt_connector-private-key" not in repr(client)
        assert client.inbox.unread().items == []
        assert inbox_authorization == ["Bearer agt_connector-private-key"]
    finally:
        client.close()
