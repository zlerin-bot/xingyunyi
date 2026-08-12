from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from agentpost_mcp.config import Settings
from agentpost_mcp.results import failure, success
from agentpost_mcp.server import create_server
from agentpost_sdk import ProtocolError
from mcp import Client


class FakeClient:
    def __init__(self, calls: list[tuple[str, object]]) -> None:
        self.calls = calls
        self.inbox = SimpleNamespace(list=self._inbox)
        self.messages = SimpleNamespace(
            get=self._get,
            ack=self._ack,
            reply=self._reply,
        )

    def __enter__(self) -> FakeClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.calls.append(("close", None))

    def send(self, *args: object, **kwargs: object) -> dict[str, object]:
        self.calls.append(("send", (args, kwargs)))
        return {"message_id": "msg_sent", "content": {"body": "external"}}

    def _inbox(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(("inbox", kwargs))
        return {"items": [], "next_cursor": kwargs.get("cursor"), "has_more": False}

    def _get(self, message_id: str) -> dict[str, object]:
        self.calls.append(("get", message_id))
        return {"message_id": message_id}

    def _ack(self, message_id: str) -> dict[str, object]:
        self.calls.append(("ack", message_id))
        return {"message_id": message_id}

    def _reply(self, *args: object, **kwargs: object) -> dict[str, object]:
        self.calls.append(("reply", (args, kwargs)))
        return {"message_id": "msg_reply"}

    def search_agents(self, **kwargs: object) -> list[dict[str, str]]:
        self.calls.append(("search", kwargs))
        return [{"address": "bob@agents.local"}]


@pytest.fixture
def adapter() -> tuple[object, list[tuple[str, object]]]:
    calls: list[tuple[str, object]] = []
    server = create_server(
        Settings("http://example.test", "agt_secret", 30, "WARNING"),
        create_client=lambda: FakeClient(calls),
    )
    return server, calls


@pytest.mark.anyio
async def test_v2_tool_contract_and_calls(adapter: tuple[object, list[tuple[str, object]]]) -> None:
    server, calls = adapter
    async with Client(server) as client:  # type: ignore[arg-type]
        listed = await client.list_tools()
        assert [tool.name for tool in listed.tools] == [
            "agentpost_send_message",
            "agentpost_list_inbox",
            "agentpost_read_message",
            "agentpost_reply",
            "agentpost_ack",
            "agentpost_search_directory",
        ]
        annotations = listed.tools[0].annotations
        assert annotations is not None
        assert annotations.read_only_hint is False
        assert annotations.open_world_hint is True

        sent = await client.call_tool(
            "agentpost_send_message",
            {"to": "bob@agents.local", "subject": "hello", "body": "world"},
        )
        assert sent.is_error is False
        assert sent.structured_content["security_label"] == "external_agent_content"
        assert json.loads(sent.content[0].text)["ok"] is True  # type: ignore[union-attr]

        page = await client.call_tool("agentpost_list_inbox", {"cursor": "opaque+/="})
        assert page.structured_content["data"]["next_cursor"] == "opaque+/="
        await client.call_tool("agentpost_read_message", {"message_id": "msg_1"})
        await client.call_tool("agentpost_reply", {"message_id": "msg_1", "body": "done"})
        await client.call_tool("agentpost_ack", {"message_id": "msg_1"})
        directory = await client.call_tool("agentpost_search_directory", {"q": "bank"})
        assert directory.structured_content["data"][0]["address"] == "bob@agents.local"

    assert [call[0] for call in calls].count("close") == 6
    assert ("get", "msg_1") in calls


def test_api_key_is_excluded_from_settings_repr() -> None:
    settings = Settings("http://example.test", "agt_top_secret", 30, "WARNING")
    assert "agt_top_secret" not in repr(settings)


def test_external_business_payload_is_opaque_while_reserved_top_level_fields_are_removed() -> None:
    result = success(
        {
            "content": {"body": {"token": "business vocabulary", "secret": "opaque data"}},
            "metadata": {"storage_key": "business field", "password": "business field"},
            "storage_key": "server-internal-object-key",
            "api_key": "server-internal-secret",
        },
        external=True,
    )

    assert result.structured_content is not None
    data = result.structured_content["data"]
    assert data["content"]["body"] == {
        "token": "business vocabulary",
        "secret": "opaque data",
    }
    assert data["metadata"] == {
        "storage_key": "business field",
        "password": "business field",
    }
    assert "storage_key" not in data
    assert "api_key" not in data
    assert result.structured_content["security_label"] == "external_agent_content"


def test_mutating_protocol_failure_is_retryable_with_same_key_and_sanitized_request_id() -> None:
    result = failure(
        ProtocolError(
            "malformed",
            status_code=201,
            code="MALFORMED_RESPONSE",
            request_id="agt_secret_must_not_escape",
            idempotency_key="mcp-reuse-this-key",
        ),
        operation="send",
    )

    assert result.structured_content is not None
    error = result.structured_content["error"]
    assert error["code"] == "AGENTPOST_PROTOCOL_ERROR"
    assert error["retryable"] is True
    assert error["acceptance_unknown"] is True
    assert error["idempotency_key"] == "mcp-reuse-this-key"
    assert "request_id" not in error
