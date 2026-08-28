from __future__ import annotations

import hashlib
import io
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest
from agentpost_sdk import (
    ApiError,
    AuthenticationError,
    ConfigurationError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ProtocolError,
    TransportError,
    ValidationError,
)

from agentpost import AgentPost

AGENT_ID = "10000000-0000-0000-0000-000000000001"
RECIPIENT_ID = "20000000-0000-0000-0000-000000000002"
DELIVERY_ID = "30000000-0000-0000-0000-000000000003"
THREAD_ID = "40000000-0000-0000-0000-000000000004"
ATTACHMENT_ID = "50000000-0000-0000-0000-000000000005"
ORGANIZATION_ID = "60000000-0000-0000-0000-000000000006"
ORGANIZATION_EVENT_ID = "70000000-0000-0000-0000-000000000007"
NOW = "2026-08-12T08:00:00Z"


def message_json(
    *,
    message_id: str = "msg_accepted",
    message_type: str = "message",
    status: str = "delivered",
    subject: str = "Greeting",
    body: Any = "Hello Bob",
    **extra: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "spec_version": "0.1",
        "message_id": message_id,
        "from": {"agent_id": AGENT_ID, "address": "alice@agents.local"},
        "to": [{"agent_id": RECIPIENT_ID, "address": "bob@agents.local"}],
        "type": message_type,
        "subject": subject,
        "content": {
            "format": "text",
            "body": body,
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
    payload.update(extra)
    return payload


def attachment_json(**extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": ATTACHMENT_ID,
        "filename": "report.pdf",
        "content_type": "application/pdf",
        "size": 7,
        "sha256": hashlib.sha256(b"PDFDATA").hexdigest(),
        "state": "pending",
        "created_at": NOW,
    }
    payload.update(extra)
    return payload


def directory_agent_json(**extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": RECIPIENT_ID,
        "address": "bob@agents.local",
        "display_name": "Bob",
        "description": "Financial researcher",
        "domain": "agents.local",
        "status": "active",
        "public_key": None,
        "capabilities": ["financial-research"],
        "endpoint": None,
        "created_at": NOW,
        "updated_at": NOW,
        "last_seen_at": None,
        "capability_verification": "self_declared",
    }
    payload.update(extra)
    return payload


def recipient_resolution_json(**extra: Any) -> dict[str, Any]:
    candidate = {
        "agent_id": RECIPIENT_ID,
        "address": "codex-f26e6148ca9297e992243fce@agentpost.me",
        "handle": "kcode",
        "display_name": "开发 Codex",
        "owner_display_name": "张子良",
        "agent_type": "codex",
        "organization_name": "产品组",
        "label": "张子良的 Codex",
        "match_kind": "human_agent",
        "security_label": "external_agent_content",
    }
    payload: dict[str, Any] = {
        "status": "resolved",
        "query": "给张子良的 Codex 发消息",
        "match": candidate,
        "candidates": [],
        "total_candidates": 1,
        "reason": "unique_match",
        "security_label": "external_agent_content",
    }
    payload.update(extra)
    return payload


def organization_channel_json(**extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "event_id": ORGANIZATION_EVENT_ID,
        "organization_id": ORGANIZATION_ID,
        "organization_slug": "research",
        "thread_id": THREAD_ID,
        "reply_to_event_id": None,
        "sender_agent_id": AGENT_ID,
        "recipient_agent_ids": [RECIPIENT_ID],
        "requested_responder_agent_ids": [RECIPIENT_ID],
        "reply_policy": "addressed_agents_reply",
        "message_ids": ["msg_group_copy"],
        "created_at": NOW,
        "replayed": False,
    }
    payload.update(extra)
    return payload


def organization_channel_summary_json(**extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "organization_id": ORGANIZATION_ID,
        "organization_slug": "research",
        "organization_name": "Research",
        "agents": [
            {
                "agent_id": RECIPIENT_ID,
                "address": "bob@agents.local",
                "handle": "bob",
                "display_name": "Bob",
            }
        ],
    }
    payload.update(extra)
    return payload


def approval_json(**extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "approval_id": "apr_0123456789abcdef",
        "requester_agent_id": AGENT_ID,
        "requester_address": "alice@agents.local",
        "action_type": "publish.report",
        "summary": "Publish a report",
        "justification": "The report is ready",
        "risk_level": "high",
        "payload": {"report_id": "report-1"},
        "status": "pending",
        "expires_at": NOW,
        "created_at": NOW,
        "updated_at": NOW,
        "decided_at": None,
        "decision_note": None,
        "security_label": "external_agent_content",
        "execution_effect": "none",
    }
    payload.update(extra)
    return payload


def json_response(
    request: httpx.Request,
    status_code: int,
    payload: Any,
    *,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    return httpx.Response(status_code, json=payload, headers=headers, request=request)


def make_client(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    api_key: str = "agt_super_secret_key",
) -> AgentPost:
    return AgentPost(
        "https://post.example/base/",
        api_key,
        transport=httpx.MockTransport(handler),
    )


def test_client_headers_base_url_user_agent_and_repr_hide_key() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return json_response(request, 200, {"items": []})

    client = make_client(handler)
    result = client.search_agents(q="bank")

    assert result == []
    assert str(seen[0].url).startswith("https://post.example/base/api/v1/directory/search?")
    assert seen[0].headers["Authorization"] == "Bearer agt_super_secret_key"
    assert seen[0].headers["User-Agent"].lower().startswith("agentpost-python/")
    assert "agt_super_secret_key" not in repr(client)
    assert "agt_super_secret_key" not in str(client)
    client.close()


def test_sdk_resolves_natural_recipient_through_verified_server_endpoint() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return json_response(request, 200, recipient_resolution_json())

    with make_client(handler) as client:
        result = client.resolve_recipient("给张子良的 Codex 发消息")

    assert seen[0].method == "POST"
    assert seen[0].url.path == "/base/api/v1/directory/resolve"
    assert json.loads(seen[0].content) == {"query": "给张子良的 Codex 发消息"}
    assert result.status == "resolved"
    assert result.match is not None
    assert result.match.handle == "kcode"
    assert result.match.label == "张子良的 Codex"
    assert result.security_label == "external_agent_content"


def test_send_builds_wire_envelope_and_task_convenience() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return json_response(request, 201, message_json(message_type="task"))

    with make_client(handler) as client:
        message = client.send(
            "researcher@agents.local",
            "Bank research",
            "Analyse the annual report",
            type="task",
            format="markdown",
            task={"instruction": "Analyse", "expected_output": "markdown report"},
            attachments=[ATTACHMENT_ID],
            priority="high",
            metadata={"case": "bank"},
            idempotency_key="sdk-send-task",
        )

    request = requests[0]
    assert request.method == "POST"
    assert request.url.path == "/base/api/v1/messages"
    assert request.headers["Idempotency-Key"] == "sdk-send-task"
    assert json.loads(request.content) == {
        "to": [{"address": "researcher@agents.local"}],
        "type": "task",
        "subject": "Bank research",
        "content": {"format": "markdown", "body": "Analyse the annual report"},
        "task": {"instruction": "Analyse", "expected_output": "markdown report"},
        "attachments": [ATTACHMENT_ID],
        "priority": "high",
        "requires_ack": True,
        "metadata": {"case": "bank"},
        "expires_at": None,
    }
    assert message.message_id == "msg_accepted"
    assert message.message_type == "task"


def test_send_organization_message_separates_context_from_requested_responder() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return json_response(request, 201, organization_channel_json())

    with make_client(handler) as client:
        event = client.send_organization_message(
            ORGANIZATION_ID,
            "Research coordination",
            "Shared context for everyone",
            requested_responder_agent_ids=[RECIPIENT_ID],
            type="task",
            task={"instruction": "Reply with the conclusion"},
            idempotency_key="sdk-organization-message",
        )

    request = requests[0]
    assert request.url.path == f"/base/api/v1/organizations/{ORGANIZATION_ID}/channel/messages"
    assert request.headers["Idempotency-Key"] == "sdk-organization-message"
    payload = json.loads(request.content)
    assert payload["requested_responder_agent_ids"] == [RECIPIENT_ID]
    assert payload["task"] == {"instruction": "Reply with the conclusion"}
    assert "to" not in payload
    assert event.event_id == UUID(ORGANIZATION_EVENT_ID)


def test_get_organization_channel_returns_current_group_and_agents() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return json_response(request, 200, organization_channel_summary_json())

    with make_client(handler) as client:
        channel = client.get_organization_channel()

    assert requests[0].method == "GET"
    assert requests[0].url.path == "/base/api/v1/organization-channel"
    assert channel.organization_name == "Research"
    assert channel.agents[0].handle == "bob"


def test_list_organization_channels_returns_every_available_group() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return json_response(request, 200, [organization_channel_summary_json()])

    with make_client(handler) as client:
        channels = client.list_organization_channels()

    assert requests[0].method == "GET"
    assert requests[0].url.path == "/base/api/v1/organization-channels"
    assert channels[0].organization_name == "Research"


def test_task_send_infers_instruction_and_rejects_invalid_type_combinations() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return json_response(request, 201, message_json(message_type="task"))

    with make_client(handler) as client:
        inferred = client.send(
            "bob@agents.local",
            "Analyse",
            "Analyse the attached report",
            type="task",
            idempotency_key="inferred-task",
        )
        with pytest.raises(ConfigurationError):
            client.send(
                "bob@agents.local",
                "Result",
                "Cannot start a result",
                type="result",
            )
        with pytest.raises(ConfigurationError):
            client.send(
                "bob@agents.local",
                "Not a task",
                "Hello",
                task={"instruction": "Unexpected"},
            )

    assert inferred.message_type == "task"
    assert json.loads(requests[0].content)["task"] == {"instruction": "Analyse the attached report"}
    assert len(requests) == 1


def test_send_accepts_idempotent_replay_200_and_exposes_header() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(
            request,
            200,
            message_json(),
            headers={"Idempotency-Replayed": "true"},
        )

    with make_client(handler) as client:
        message = client.send(
            "bob@agents.local",
            "Greeting",
            "Hello Bob",
            idempotency_key="replay-key",
        )

    assert message.message_id == "msg_accepted"
    assert message.idempotency_replayed is True


def test_transport_error_exposes_generated_key_for_explicit_safe_reuse() -> None:
    keys: list[str] = []
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        keys.append(request.headers["Idempotency-Key"])
        if calls == 1:
            raise httpx.ConnectError("offline", request=request)
        return json_response(request, 201, message_json())

    with make_client(handler) as client:
        with pytest.raises(TransportError) as raised:
            client.send("bob@agents.local", "Greeting", "Hello")
        generated_key = raised.value.idempotency_key
        assert isinstance(generated_key, str) and generated_key
        result = client.send(
            "bob@agents.local",
            "Greeting",
            "Hello",
            idempotency_key=generated_key,
        )

    assert result.message_id == "msg_accepted"
    assert keys == [generated_key, generated_key]
    assert calls == 2


def test_inbox_filters_unread_and_cursor_remains_opaque() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return json_response(
            request,
            200,
            {
                "items": [message_json()],
                "next_cursor": "opaque+/==.signed-token",
                "has_more": True,
            },
        )

    with make_client(handler) as client:
        page = client.inbox.list(
            status="read",
            sender="alice@agents.local",
            type="task",
            priority="urgent",
            since=datetime(2026, 8, 12, tzinfo=UTC),
            limit=7,
            cursor="input+/==.opaque",
        )
        unread = client.inbox.unread(limit=3, cursor=page.next_cursor)

    first = dict(requests[0].url.params)
    assert first == {
        "status": "read",
        "sender": "alice@agents.local",
        "type": "task",
        "priority": "urgent",
        "since": "2026-08-12T00:00:00+00:00",
        "limit": "7",
        "cursor": "input+/==.opaque",
    }
    second = dict(requests[1].url.params)
    assert second["status"] == "unread"
    assert second["cursor"] == "opaque+/==.signed-token"
    assert page.has_more is True
    assert page.items[0].message_id == "msg_accepted"
    assert unread.next_cursor == "opaque+/==.signed-token"


def test_inbox_omits_unset_optional_query_parameters() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return json_response(
            request,
            200,
            {"items": [], "next_cursor": None, "has_more": False},
        )

    with make_client(handler) as client:
        client.inbox.unread()

    assert dict(requests[0].url.params) == {"status": "unread", "limit": "50"}


def test_get_read_ack_and_bound_message_methods() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        status = "delivered"
        if request.url.path.endswith("/read"):
            status = "read"
        elif request.url.path.endswith("/ack"):
            status = "acked"
        return json_response(request, 200, message_json(status=status))

    with make_client(handler) as client:
        fetched = client.messages.get("msg_accepted")
        assert client.messages.read("msg_accepted").delivery.status == "read"
        assert client.messages.ack("msg_accepted").delivery.status == "acked"
        assert fetched.read().delivery.status == "read"
        assert fetched.ack().delivery.status == "acked"

    assert [(request.method, request.url.path) for request in requests] == [
        ("GET", "/base/api/v1/messages/msg_accepted"),
        ("POST", "/base/api/v1/messages/msg_accepted/read"),
        ("POST", "/base/api/v1/messages/msg_accepted/ack"),
        ("POST", "/base/api/v1/messages/msg_accepted/read"),
        ("POST", "/base/api/v1/messages/msg_accepted/ack"),
    ]


def test_reply_service_and_bound_method_build_the_same_safe_route() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return json_response(request, 200, message_json())
        return json_response(
            request,
            201,
            message_json(message_id="msg_reply", message_type="result"),
        )

    with make_client(handler) as client:
        parent = client.messages.get("msg_accepted")
        direct = client.messages.reply(
            parent.message_id,
            "Completed",
            type="result",
            result={"status": "completed", "summary": "Done"},
            idempotency_key="direct-reply",
        )
        bound = parent.reply("Received", idempotency_key="bound-reply")

    replies = requests[1:]
    assert all(
        request.url.path == "/base/api/v1/messages/msg_accepted/reply" for request in replies
    )
    assert replies[0].headers["Idempotency-Key"] == "direct-reply"
    assert json.loads(replies[0].content)["result"] == {
        "status": "completed",
        "summary": "Done",
    }
    assert replies[1].headers["Idempotency-Key"] == "bound-reply"
    assert direct.message_id == bound.message_id == "msg_reply"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"type": "result"},
        {"type": "message", "result": {"status": "completed"}},
        {"type": "message", "task": {"instruction": "Unexpected"}},
        {"type": "message", "format": "xml"},
    ],
)
def test_reply_rejects_invalid_semantic_combinations_without_http(
    kwargs: dict[str, Any],
) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return json_response(request, 201, message_json(message_id="msg_reply"))

    with make_client(handler) as client, pytest.raises(ConfigurationError):
        client.messages.reply("msg_parent", "Body", **kwargs)

    assert calls == 0


def test_directory_search_encodes_only_supplied_filters() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return json_response(request, 200, {"items": [directory_agent_json()]})

    with make_client(handler) as client:
        agents = client.search_agents(q="bank & finance", capability="financial-research")

    assert dict(requests[0].url.params) == {
        "q": "bank & finance",
        "capability": "financial-research",
        "limit": "20",
    }
    assert agents[0].address == "bob@agents.local"
    assert agents[0].capabilities == ["financial-research"]


def test_directory_search_omits_unset_optional_query_parameters() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return json_response(request, 200, {"items": []})

    with make_client(handler) as client:
        assert client.search_agents(q="bank") == []

    assert dict(requests[0].url.params) == {"q": "bank", "limit": "20"}


def test_directory_search_requires_a_filter_without_an_http_request() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return json_response(request, 200, {"items": []})

    with make_client(handler) as client, pytest.raises(ConfigurationError):
        client.search_agents()

    assert requests == []


def test_upload_uses_multipart_without_loading_a_path_name_into_json(tmp_path: Path) -> None:
    source = tmp_path / "report.pdf"
    source.write_bytes(b"PDFDATA")
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return json_response(request, 201, attachment_json())

    memory = io.BytesIO(b"PDFDATA")
    with make_client(handler) as client:
        attachment = client.attachments.upload(source, content_type="application/pdf")
        from_memory = client.attachments.upload(
            memory,
            filename="memory.pdf",
            content_type="application/pdf",
        )

    assert str(attachment.id) == ATTACHMENT_ID
    assert str(from_memory.id) == ATTACHMENT_ID
    assert memory.closed is False
    for request, filename in zip(requests, ["report.pdf", "memory.pdf"], strict=True):
        assert request.method == "POST"
        assert request.url.path == "/base/api/v1/attachments"
        assert request.headers["Content-Type"].startswith("multipart/form-data; boundary=")
        body = request.content
        assert b' name="file"' in body
        assert f'filename="{filename}"'.encode() in body
        assert b"Content-Type: application/pdf" in body
        assert b"PDFDATA" in body


def test_download_is_atomic_verifies_sha_and_cleans_partial_files(tmp_path: Path) -> None:
    destination = tmp_path / "download.bin"
    destination.write_bytes(b"ORIGINAL")
    expected = hashlib.sha256(b"NEW CONTENT").hexdigest()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"NEW CONTENT", request=request)

    with make_client(handler) as client:
        downloaded = client.attachments.download(
            ATTACHMENT_ID,
            destination,
            expected_sha256=expected,
        )

    assert destination.read_bytes() == b"NEW CONTENT"
    assert downloaded.path == destination
    assert downloaded.sha256 == expected
    assert downloaded.size == len(b"NEW CONTENT")
    assert not list(tmp_path.glob("*.part"))

    destination.write_bytes(b"KEEP ME")
    with make_client(handler) as client:
        with pytest.raises(ProtocolError):
            client.attachments.download(
                ATTACHMENT_ID,
                destination,
                expected_sha256="0" * 64,
            )
    assert destination.read_bytes() == b"KEEP ME"
    assert not list(tmp_path.glob("*.part"))


def test_download_transport_failure_preserves_destination_and_cleans_partial(
    tmp_path: Path,
) -> None:
    class BrokenStream(httpx.SyncByteStream):
        def __iter__(self):
            yield b"PARTIAL"
            raise httpx.ReadError("connection lost")

    destination = tmp_path / "download.bin"
    destination.write_bytes(b"ORIGINAL")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=BrokenStream(), request=request)

    with make_client(handler) as client, pytest.raises(TransportError):
        client.attachments.download(ATTACHMENT_ID, destination)

    assert destination.read_bytes() == b"ORIGINAL"
    assert not list(tmp_path.glob("*.part"))


@pytest.mark.parametrize(
    ("status_code", "error_type"),
    [
        (401, AuthenticationError),
        (403, ForbiddenError),
        (404, NotFoundError),
        (409, ConflictError),
        (422, ValidationError),
        (500, ApiError),
    ],
)
def test_error_envelope_maps_status_to_typed_exception(
    status_code: int,
    error_type: type[ApiError],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(
            request,
            status_code,
            {
                "error": {
                    "code": "TEST_FAILURE",
                    "message": "Safe message",
                    "request_id": "request-123",
                    "details": {"field": "value"},
                    "future_error_field": "ignored",
                }
            },
        )

    with make_client(handler) as client, pytest.raises(error_type) as raised:
        client.messages.get("msg_missing")

    assert raised.value.status_code == status_code
    assert raised.value.code == "TEST_FAILURE"
    assert raised.value.request_id == "request-123"
    assert raised.value.details == {"field": "value"}
    assert "agt_super_secret_key" not in repr(raised.value)


def test_malformed_success_json_raises_protocol_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="not-json",
            headers={"Content-Type": "application/json"},
            request=request,
        )

    with make_client(handler) as client, pytest.raises(ProtocolError):
        client.messages.get("msg_invalid")


def test_unknown_response_fields_and_message_types_are_forward_compatible() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(
            request,
            200,
            message_json(
                message_type="future-artifact",
                future_top_level={"new": True},
                delivery=message_json()["delivery"] | {"future_delivery_field": 1},
            ),
        )

    with make_client(handler) as client:
        message = client.messages.get("msg_future")

    assert message.message_type == "future-artifact"
    assert message.message_id == "msg_accepted"


def test_context_manager_closes_transport() -> None:
    class TrackingTransport(httpx.MockTransport):
        closed = False

        def close(self) -> None:
            self.closed = True
            super().close()

    transport = TrackingTransport(lambda request: json_response(request, 200, {"items": []}))
    with AgentPost(
        "https://post.example",
        "agt_key",
        transport=transport,
    ) as client:
        assert client.search_agents(q="any") == []
        assert transport.closed is False
    assert transport.closed is True


def test_api_failures_are_not_retried_implicitly() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return json_response(
            request,
            503,
            {
                "error": {
                    "code": "TEMPORARILY_UNAVAILABLE",
                    "message": "Try later",
                    "request_id": "request-503",
                    "details": {},
                }
            },
        )

    with make_client(handler) as client, pytest.raises(ApiError):
        client.messages.get("msg_once")

    assert calls == 1


def test_approval_resource_create_replay_list_poll_and_cancel() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST" and request.url.path.endswith("/approval-requests"):
            return json_response(
                request,
                200,
                approval_json(),
                headers={"Idempotency-Replayed": "true"},
            )
        if request.method == "GET" and request.url.path.endswith("/approval-requests"):
            return json_response(request, 200, {"items": [approval_json()]})
        if request.method == "GET":
            return json_response(request, 200, approval_json(status="approved"))
        return json_response(request, 200, approval_json(status="cancelled"))

    with make_client(handler) as client:
        created = client.approvals.create(
            "publish.report",
            "Publish a report",
            justification="Ready",
            risk_level="high",
            payload={"report_id": "report-1"},
            idempotency_key="approval-sdk-key",
        )
        page = client.approvals.list(status="pending", limit=10)
        polled = client.approvals.get(created.approval_id)
        cancelled = client.approvals.cancel(created.approval_id)

    assert created.idempotency_replayed is True
    assert created.security_label == "external_agent_content"
    assert created.execution_effect == "none"
    create_request = requests[0]
    assert create_request.headers["Idempotency-Key"] == "approval-sdk-key"
    assert json.loads(create_request.content)["payload"] == {"report_id": "report-1"}
    assert requests[1].url.params["status"] == "pending"
    assert requests[1].url.params["limit"] == "10"
    assert page.items[0].approval_id == created.approval_id
    assert polled.status == "approved"
    assert cancelled.status == "cancelled"


def test_approval_transport_failure_exposes_idempotency_key_without_retry() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("offline")

    with make_client(handler) as client, pytest.raises(TransportError) as raised:
        client.approvals.create(
            "publish.report",
            "Publish a report",
            idempotency_key="approval-safe-retry",
        )

    assert calls == 1
    assert raised.value.idempotency_key == "approval-safe-retry"
