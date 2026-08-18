from __future__ import annotations

import httpx
import pytest
from agentpost_mcp.remote import (
    REMOTE_SCOPE,
    AgentPostTokenVerifier,
    RemoteSettings,
    create_remote_server,
    remote_client_factory,
)
from agentpost_sdk import ConfigurationError
from mcp.server.auth.middleware.auth_context import auth_context_var
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from mcp.server.auth.provider import AccessToken
from mcp.server.transport_security import TransportSecuritySettings
from starlette.testclient import TestClient

EXPECTED_TOOLS = {
    "agentpost_send_message",
    "agentpost_list_inbox",
    "agentpost_read_message",
    "agentpost_reply",
    "agentpost_ack",
    "agentpost_search_directory",
}


def settings() -> RemoteSettings:
    return RemoteSettings(
        server="https://api.example.test",
        issuer_url="https://issuer.example.test",
        resource_url="https://mcp.example.test/mcp",
        host="127.0.0.1",
        port=8001,
        timeout_seconds=30,
        log_level="WARNING",
        allowed_hosts=("mcp.example.test", "testserver"),
        allowed_origins=("https://mcp.example.test",),
    )


@pytest.mark.anyio
async def test_remote_token_verifier_uses_safe_token_info_contract() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "active": True,
                "client_id": "agentpost-remote-mcp",
                "scope": REMOTE_SCOPE,
                "resource": "https://mcp.example.test/mcp",
                "sub": "10000000-0000-0000-0000-000000000001",
                "connector_id": "con_remote",
                "exp": 2_000_000_000,
            },
            request=request,
        )

    verifier = AgentPostTokenVerifier(settings(), transport=httpx.MockTransport(handler))
    token = await verifier.verify_token("oat_private_token_material")
    assert token is not None
    assert token.scopes == [REMOTE_SCOPE]
    assert token.resource == "https://mcp.example.test/mcp"
    assert seen[0].url.path == "/api/v1/oauth/token-info"
    assert seen[0].headers["Authorization"] == "Bearer oat_private_token_material"

    wrong_resource = AgentPostTokenVerifier(
        settings(),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "active": True,
                    "client_id": "agentpost-remote-mcp",
                    "scope": REMOTE_SCOPE,
                    "resource": "https://attacker.example/mcp",
                    "sub": "agent",
                    "exp": 2_000_000_000,
                },
                request=request,
            )
        ),
    )
    assert await wrong_resource.verify_token("oat_private_token_material") is None


def test_remote_client_factory_binds_oauth_context_without_exposing_token() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"items": []}, request=request)

    access = AccessToken(
        token="oat_private_token_material",
        client_id="agentpost-remote-mcp",
        scopes=[REMOTE_SCOPE],
        expires_at=2_000_000_000,
        resource="https://mcp.example.test/mcp",
        subject="10000000-0000-0000-0000-000000000001",
    )
    context = auth_context_var.set(AuthenticatedUser(access))
    try:
        with remote_client_factory(settings(), transport=httpx.MockTransport(handler))() as client:
            assert client.search_agents(q="bank") == []
            assert "oat_private" not in repr(client)
    finally:
        auth_context_var.reset(context)
    assert requests[0].headers["Authorization"] == "Bearer oat_private_token_material"

    with pytest.raises(ConfigurationError):
        remote_client_factory(settings())()


def test_remote_server_has_six_tools_and_requires_bearer_auth() -> None:
    class RejectAll:
        async def verify_token(self, token: str) -> AccessToken | None:
            del token
            return None

    server = create_remote_server(settings(), token_verifier=RejectAll())
    assert {tool.name for tool in server._tool_manager.list_tools()} == EXPECTED_TOOLS
    app = server.streamable_http_app(
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
        transport_security=TransportSecuritySettings(
            allowed_hosts=["testserver"],
            allowed_origins=["https://mcp.example.test"],
        ),
    )
    with TestClient(app) as client:
        unauthorized = client.post(
            "/mcp",
            headers={"MCP-Protocol-Version": "2026-07-28"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
        metadata = client.get("/.well-known/oauth-protected-resource/mcp")
    assert unauthorized.status_code == 401
    assert "resource_metadata=" in unauthorized.headers["WWW-Authenticate"]
    assert metadata.status_code == 200
    assert metadata.json()["authorization_servers"] == ["https://issuer.example.test"]


def test_remote_settings_reject_credentials_and_unbounded_transport(monkeypatch) -> None:
    monkeypatch.setenv("AGENTPOST_SERVER", "https://user:secret@example.test")
    with pytest.raises(ConfigurationError):
        RemoteSettings.from_env()
    monkeypatch.setenv("AGENTPOST_SERVER", "https://api.example.test")
    monkeypatch.setenv("AGENTPOST_MCP_RESOURCE_URL", "https://mcp.example.test/not-mcp")
    with pytest.raises(ConfigurationError):
        RemoteSettings.from_env()
