from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

pytest.importorskip("mcp", reason="optional MCP v2 extra is not installed")

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MCP_SOURCE = REPOSITORY_ROOT / "integrations" / "mcp" / "src"
SDK_SOURCE = REPOSITORY_ROOT / "sdk" / "python" / "src"
for source in (MCP_SOURCE, SDK_SOURCE):
    value = str(source)
    if value not in sys.path:
        sys.path.insert(0, value)

from agentpost_mcp.config import Settings  # noqa: E402
from agentpost_mcp.results import failure  # noqa: E402
from agentpost_mcp.server import create_server  # noqa: E402
from agentpost_mcp.tools import register_tools  # noqa: E402

from agentpost import AgentPost  # noqa: E402

AGENT_ID = "10000000-0000-0000-0000-000000000001"
RECIPIENT_ID = "20000000-0000-0000-0000-000000000002"
DELIVERY_ID = "30000000-0000-0000-0000-000000000003"
THREAD_ID = "40000000-0000-0000-0000-000000000004"
NOW = "2026-08-12T08:00:00Z"

EXPECTED_TOOLS = {
    "agentpost_resolve_recipient",
    "agentpost_send_message",
    "agentpost_get_organization_channel",
    "agentpost_list_organization_channels",
    "agentpost_send_organization_message",
    "agentpost_list_inbox",
    "agentpost_read_message",
    "agentpost_reply",
    "agentpost_ack",
    "agentpost_search_directory",
}


def message_json(
    *,
    message_id: str = "msg_accepted",
    status: str = "delivered",
    message_type: str = "message",
) -> dict[str, Any]:
    return {
        "spec_version": "0.1",
        "message_id": message_id,
        "from": {"agent_id": AGENT_ID, "address": "alice@agents.local"},
        "to": [{"agent_id": RECIPIENT_ID, "address": "bob@agents.local"}],
        "type": message_type,
        "subject": "Greeting",
        "content": {
            "format": "text",
            "body": "external content",
            "security_label": "external_agent_content",
        },
        "attachments": [],
        "thread_id": THREAD_ID,
        "reply_to": None,
        "priority": "normal",
        "requires_ack": True,
        "metadata": {},
        "created_at": NOW,
        "accepted_at": NOW,
        "expires_at": None,
        "delivery": {
            "delivery_id": DELIVERY_ID,
            "recipient_agent_id": RECIPIENT_ID,
            "inbox_seq": 1,
            "status": status,
            "delivery_attempts": 1,
            "delivered_at": NOW,
            "read_at": NOW if status in {"read", "acked"} else None,
            "acked_at": NOW if status == "acked" else None,
            "error": None,
        },
    }


class ToolRegistration:
    def __init__(self, function: Callable[..., Any], metadata: dict[str, Any]) -> None:
        self.function = function
        self.metadata = metadata


class FakeMCP:
    def __init__(self) -> None:
        self.registrations: dict[str, ToolRegistration] = {}

    def tool(self, **metadata: Any):
        def decorate(function: Callable[..., Any]) -> Callable[..., Any]:
            name = str(metadata["name"])
            assert name not in self.registrations
            self.registrations[name] = ToolRegistration(function, metadata)
            return function

        return decorate


def registered_tools(
    handler: Callable[[httpx.Request], httpx.Response],
) -> tuple[FakeMCP, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def capture(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    transport = httpx.MockTransport(capture)

    def create_client() -> AgentPost:
        return AgentPost(
            "https://post.example/root",
            "agt_mcp_secret_that_must_not_leak",
            transport=transport,
        )

    mcp = FakeMCP()
    register_tools(mcp, create_client)
    return mcp, requests


def structured(result: Any) -> dict[str, Any]:
    payload = result.structured_content
    assert isinstance(payload, dict)
    text_payload = json.loads(result.content[0].text)
    assert text_payload == payload
    return payload


def test_exact_nine_tools_have_strict_public_parameters_and_v2_annotations() -> None:
    mcp, _ = registered_tools(
        lambda request: httpx.Response(200, json={"items": []}, request=request)
    )
    assert set(mcp.registrations) == EXPECTED_TOOLS

    forbidden = {"server", "base_url", "url", "endpoint", "api_key", "timeout"}
    for name, registration in mcp.registrations.items():
        signature = inspect.signature(registration.function)
        assert forbidden.isdisjoint(signature.parameters), name
        assert registration.metadata["structured_output"] is False
        annotations = registration.metadata["annotations"]
        assert annotations.destructive_hint is False
        assert annotations.open_world_hint is True
        if name in {
            "agentpost_list_inbox",
            "agentpost_read_message",
            "agentpost_resolve_recipient",
            "agentpost_search_directory",
            "agentpost_get_organization_channel",
            "agentpost_list_organization_channels",
        }:
            assert annotations.read_only_hint is True
            assert annotations.idempotent_hint is True
        elif name == "agentpost_ack":
            assert annotations.read_only_hint is False
            assert annotations.idempotent_hint is True
        else:
            assert annotations.read_only_hint is False
            assert annotations.idempotent_hint is False


def test_real_mcp_v2_server_exports_exact_schemas_and_sync_tool_contracts() -> None:
    server = create_server(
        Settings(
            server="https://post.example",
            api_key="agt_server_secret_that_must_not_leak",
            timeout_seconds=30,
            log_level="WARNING",
        )
    )
    tools = {tool.name: tool for tool in server._tool_manager.list_tools()}
    assert set(tools) == EXPECTED_TOOLS
    # MCP v2 executes registered synchronous functions via its worker-thread path.
    assert all(tool.is_async is False for tool in tools.values())

    send = tools["agentpost_send_message"].parameters
    organization_send = tools["agentpost_send_organization_message"].parameters
    reply = tools["agentpost_reply"].parameters
    inbox = tools["agentpost_list_inbox"].parameters
    assert "result" not in send["properties"]["message_type"]["enum"]
    assert "result" in reply["properties"]["message_type"]["enum"]
    for schema in (send, organization_send, reply):
        idempotency = schema["properties"]["idempotency_key"]["anyOf"][0]
        assert idempotency["minLength"] == 1
        assert idempotency["maxLength"] == 255
    organization_attachments = organization_send["properties"]["attachment_ids"]["anyOf"][0]
    assert organization_attachments["maxItems"] == 32
    assert organization_send["properties"]["attachment_ids"]["uniqueItems"] is True
    cursor = inbox["properties"]["cursor"]["anyOf"][0]
    assert cursor["type"] == "string"
    assert cursor["maxLength"] == 2048
    for name in ("agentpost_read_message", "agentpost_reply", "agentpost_ack"):
        message_id = tools[name].parameters["properties"]["message_id"]
        assert message_id["minLength"] == 1
        assert message_id["maxLength"] == 64
    for tool in tools.values():
        serialized = json.dumps(tool.parameters).casefold()
        assert all(
            forbidden not in serialized
            for forbidden in ("api_key", "apikey", "server", "base_url", "endpoint")
        )


def test_read_and_inbox_are_get_only_and_cursor_is_opaque() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/inbox"):
            return httpx.Response(
                200,
                json={
                    "items": [message_json()],
                    "next_cursor": "opaque+/==.signed",
                    "has_more": True,
                },
                request=request,
            )
        return httpx.Response(200, json=message_json(), request=request)

    mcp, requests = registered_tools(handler)
    inbox = mcp.registrations["agentpost_list_inbox"].function(
        status="unread",
        cursor="input+/==.opaque",
        limit=7,
    )
    read = mcp.registrations["agentpost_read_message"].function("msg_accepted")

    assert [(request.method, request.url.path) for request in requests] == [
        ("GET", "/root/api/v1/inbox"),
        ("GET", "/root/api/v1/messages/msg_accepted"),
    ]
    assert dict(requests[0].url.params) == {
        "status": "unread",
        "limit": "7",
        "cursor": "input+/==.opaque",
    }
    assert structured(inbox)["data"]["next_cursor"] == "opaque+/==.signed"
    assert structured(inbox)["security_label"] == "external_agent_content"
    assert structured(read)["security_label"] == "external_agent_content"
    assert all("/read" not in request.url.path for request in requests)


def test_send_reply_ack_and_search_map_to_the_public_http_protocol() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/directory/resolve"):
            return httpx.Response(
                200,
                json={
                    "status": "resolved",
                    "query": "给 kcode 发消息",
                    "match": {
                        "agent_id": RECIPIENT_ID,
                        "address": "bob@agents.local",
                        "handle": "kcode",
                        "display_name": "Bob",
                        "owner_display_name": "张子良",
                        "agent_type": "codex",
                        "organization_name": None,
                        "label": "张子良的 Codex",
                        "match_kind": "handle",
                        "security_label": "external_agent_content",
                    },
                    "candidates": [],
                    "total_candidates": 1,
                    "reason": "unique_match",
                    "security_label": "external_agent_content",
                },
                request=request,
            )
        if request.url.path.endswith("/directory/search"):
            return httpx.Response(200, json={"items": []}, request=request)
        status = "acked" if request.url.path.endswith("/ack") else "delivered"
        return httpx.Response(201, json=message_json(status=status), request=request)

    mcp, requests = registered_tools(handler)
    sent = mcp.registrations["agentpost_send_message"].function(
        "bob@agents.local",
        "Task",
        "Analyse",
        message_type="task",
        task={"instruction": "Analyse"},
        idempotency_key="mcp-send-reusable",
    )
    reply = mcp.registrations["agentpost_reply"].function(
        "msg_accepted",
        "Completed",
        message_type="result",
        result={"status": "completed"},
        idempotency_key="mcp-reply-reusable",
    )
    ack = mcp.registrations["agentpost_ack"].function("msg_accepted")
    resolved = mcp.registrations["agentpost_resolve_recipient"].function("给 kcode 发消息")
    search = mcp.registrations["agentpost_search_directory"].function(
        capability="financial-research"
    )

    assert [(request.method, request.url.path) for request in requests] == [
        ("POST", "/root/api/v1/messages"),
        ("POST", "/root/api/v1/messages/msg_accepted/reply"),
        ("POST", "/root/api/v1/messages/msg_accepted/ack"),
        ("POST", "/root/api/v1/directory/resolve"),
        ("GET", "/root/api/v1/directory/search"),
    ]
    assert requests[0].headers["Idempotency-Key"] == "mcp-send-reusable"
    assert requests[1].headers["Idempotency-Key"] == "mcp-reply-reusable"
    assert json.loads(requests[0].content)["type"] == "task"
    assert json.loads(requests[1].content)["type"] == "result"
    assert json.loads(requests[3].content) == {"query": "给 kcode 发消息"}
    assert dict(requests[4].url.params) == {
        "capability": "financial-research",
        "limit": "20",
    }
    for result in (sent, reply, ack, resolved, search):
        assert structured(result)["security_label"] == "external_agent_content"


def test_transport_failure_is_not_retried_and_exposes_generated_reusable_key() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("secret network detail", request=request)

    mcp, _ = registered_tools(handler)
    result = mcp.registrations["agentpost_send_message"].function(
        "bob@agents.local", "Greeting", "Hello"
    )
    payload = structured(result)

    assert calls == 1
    assert result.is_error is True
    assert payload["ok"] is False
    error = payload["error"]
    assert error["code"] == "AGENTPOST_TRANSPORT_ERROR"
    assert error["acceptance_unknown"] is True
    assert error["retryable"] is True
    assert isinstance(error["idempotency_key"], str) and error["idempotency_key"]
    assert "secret network detail" not in json.dumps(payload)


def test_http_errors_expose_only_stable_fields_and_never_echo_secrets() -> None:
    api_key = "agt_mcp_secret_that_must_not_leak"
    raw_secret = "server-raw-secret"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "error": {
                    "code": "DELIVERY_NOT_ALLOWED",
                    "message": "sensitive upstream message",
                    "request_id": "request-403",
                    "details": {
                        "authorization": api_key,
                        "raw_body": raw_secret,
                    },
                }
            },
            headers={"Authorization": api_key},
            request=request,
        )

    mcp, _ = registered_tools(handler)
    result = mcp.registrations["agentpost_read_message"].function("msg_forbidden")
    payload = structured(result)
    rendered = json.dumps(payload)

    assert result.is_error is True
    assert payload["error"]["code"] == "DELIVERY_NOT_ALLOWED"
    assert payload["error"]["message"] == "AgentPost request failed"
    assert payload["error"]["request_id"] == "request-403"
    assert "details" not in payload["error"]
    assert api_key not in rendered
    assert raw_secret not in rendered
    assert "sensitive upstream message" not in rendered


def test_core_remains_independent_and_stdio_code_never_prints_protocol_noise() -> None:
    core_sources = "\n".join(
        path.read_text(encoding="utf-8") for path in (REPOSITORY_ROOT / "src").rglob("*.py")
    )
    adapter_sources = "\n".join(
        path.read_text(encoding="utf-8") for path in MCP_SOURCE.rglob("*.py")
    )
    assert "agentpost_mcp" not in core_sources
    assert "print(" not in adapter_sources
    assert "sys.stdout" not in adapter_sources

    project = (REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'mcp = ["mcp>=2.0.0,<3"]' in project
    core_init = (REPOSITORY_ROOT / "src" / "agentpost" / "__init__.py").read_text(encoding="utf-8")
    assert "from mcp" not in core_init


def test_stdio_configuration_failure_never_pollutes_stdout_or_echoes_secrets() -> None:
    environment = os.environ.copy()
    environment.pop("AGENTPOST_API_KEY", None)
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(REPOSITORY_ROOT / "src"), str(SDK_SOURCE), str(MCP_SOURCE)]
    )
    completed = subprocess.run(
        [sys.executable, "-m", "agentpost_mcp"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert completed.returncode == 2
    assert completed.stdout == ""
    assert "AGENTPOST_API_KEY or AGENTPOST_PROFILE is required" in completed.stderr
    assert "agt_" not in completed.stderr


def test_settings_and_unexpected_failure_logging_do_not_expose_api_keys(caplog) -> None:
    api_key = "agt_exception_secret_that_must_not_leak"
    settings = Settings(
        server="https://post.example",
        api_key=api_key,
        timeout_seconds=30,
        log_level="WARNING",
    )
    assert api_key not in repr(settings)

    with caplog.at_level("ERROR"):
        result = failure(RuntimeError(f"unexpected {api_key}"), operation="read_message")
    assert structured(result)["error"]["code"] == "INTERNAL_ERROR"
    assert api_key not in caplog.text
