"""Credential-safe AgentPost adapter for a Manus local-folder task."""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, BinaryIO

from agentpost_sdk.client import AgentPost
from agentpost_sdk.connector import KeyringCredentialStore
from agentpost_sdk.errors import AgentPostError, ConfigurationError

SCHEMA_VERSION = 1
MAX_REQUEST_BYTES = 1024 * 1024


class ManusLocalAdapterError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_path(adapter_path: Path) -> Path:
    return adapter_path.with_name(".xingyunyi.json")


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ManusLocalAdapterError("manus_local_manifest_invalid")
    return value.strip()


def _load_manifest(adapter_path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(_manifest_path(adapter_path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ManusLocalAdapterError("manus_local_manifest_missing") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ManusLocalAdapterError("manus_local_manifest_invalid") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise ManusLocalAdapterError("manus_local_manifest_invalid")
    agents_path = adapter_path.with_name("AGENTS.md")
    if not agents_path.is_file():
        raise ManusLocalAdapterError("manus_agents_md_missing")
    try:
        if _sha256(adapter_path) != _required_text(payload, "adapter_sha256"):
            raise ManusLocalAdapterError("manus_local_adapter_integrity_failed")
        if _sha256(agents_path) != _required_text(payload, "agents_sha256"):
            raise ManusLocalAdapterError("manus_agents_md_integrity_failed")
    except OSError as exc:
        raise ManusLocalAdapterError("manus_local_adapter_integrity_failed") from exc
    _required_text(payload, "server")
    _required_text(payload, "profile")
    _required_text(payload, "expected_agent_address")
    return payload


@contextmanager
def _client(
    manifest: dict[str, Any],
    *,
    credential_store: KeyringCredentialStore | None = None,
    client_factory=AgentPost,
) -> Iterator[tuple[AgentPost, Any]]:
    server = _required_text(manifest, "server").rstrip("/")
    profile = _required_text(manifest, "profile")
    store = credential_store or KeyringCredentialStore()
    credential = store.load(server=server, profile=profile)
    if credential is None:
        raise ManusLocalAdapterError("manus_vault_profile_missing")
    client = client_factory(server, credential.api_key)
    client._connector_id = credential.connector_id
    client._agent_address = credential.agent_address
    try:
        yield client, credential
    finally:
        client.close()


def _message_payload(message: Any) -> dict[str, Any]:
    return message.model_dump(mode="json", by_alias=True)


def _heartbeat(client: AgentPost, expected_address: str) -> dict[str, Any]:
    try:
        heartbeat = client.connector.heartbeat()
    except AgentPostError as exc:
        raise ManusLocalAdapterError("manus_local_status_failed") from exc
    if heartbeat.agent.address != expected_address:
        raise ManusLocalAdapterError("manus_identity_mismatch")
    if not heartbeat.current:
        raise ManusLocalAdapterError("manus_identity_mismatch")
    if heartbeat.connector.status != "active" or heartbeat.connector.health_status != "healthy":
        raise ManusLocalAdapterError("manus_local_status_failed")
    return {
        "status": "ok",
        "current": True,
        "agent_address": heartbeat.agent.address,
        "connector": {
            "status": heartbeat.connector.status,
            "health_status": heartbeat.connector.health_status,
        },
    }


def _request_payload(stream: BinaryIO) -> dict[str, Any]:
    raw = stream.read(MAX_REQUEST_BYTES + 1)
    if len(raw) > MAX_REQUEST_BYTES:
        raise ManusLocalAdapterError("manus_request_too_large")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ManusLocalAdapterError("manus_request_invalid") from exc
    if not isinstance(payload, dict):
        raise ManusLocalAdapterError("manus_request_invalid")
    return payload


def _text(payload: dict[str, Any], key: str, *, required: bool = True) -> str:
    value = payload.get(key, "")
    if not isinstance(value, str) or (required and not value.strip()):
        raise ManusLocalAdapterError("manus_request_invalid")
    return value


def _run_request(client: AgentPost, payload: dict[str, Any]) -> dict[str, Any]:
    operation = _text(payload, "operation")
    if operation == "send":
        to = _text(payload, "to", required=False).strip()
        recipient = _text(payload, "recipient", required=False).strip()
        if bool(to) == bool(recipient):
            raise ManusLocalAdapterError("manus_recipient_invalid")
        if recipient:
            resolution = client.resolve_recipient(recipient)
            if resolution.status != "resolved" or resolution.match is None:
                return {
                    "status": resolution.status,
                    "reason": resolution.reason,
                    "candidates": [item.model_dump(mode="json") for item in resolution.candidates],
                    "security_label": "external_agent_content",
                }
            to = resolution.match.address
        message = client.send(
            to,
            _text(payload, "subject", required=False),
            payload.get("body"),
            type=_text(payload, "type", required=False) or "message",
            format=_text(payload, "format", required=False) or "text",
            priority=_text(payload, "priority", required=False) or "normal",
            requires_ack=bool(payload.get("requires_ack", True)),
            idempotency_key=_text(payload, "idempotency_key", required=False) or None,
        )
        return {"status": "accepted", "message": _message_payload(message)}
    if operation == "inbox":
        limit = payload.get("limit", 50)
        if not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ManusLocalAdapterError("manus_request_invalid")
        page = client.inbox.list(
            status=_text(payload, "status", required=False) or "unread",
            limit=limit,
        )
        return {
            "status": "ok",
            "items": [_message_payload(item) for item in page.items],
            "next_cursor": page.next_cursor,
            "has_more": page.has_more,
            "security_label": "external_agent_content",
        }
    if operation == "read":
        return {
            "status": "ok",
            "message": _message_payload(client.messages.read(_text(payload, "message_id"))),
        }
    if operation == "ack":
        return {
            "status": "ok",
            "message": _message_payload(client.messages.ack(_text(payload, "message_id"))),
        }
    if operation == "reply":
        message = client.messages.reply(
            _text(payload, "message_id"),
            payload.get("body"),
            subject=_text(payload, "subject", required=False),
            type=_text(payload, "type", required=False) or "message",
            format=_text(payload, "format", required=False) or "text",
            priority=_text(payload, "priority", required=False) or "normal",
            requires_ack=bool(payload.get("requires_ack", True)),
            idempotency_key=_text(payload, "idempotency_key", required=False) or None,
        )
        return {"status": "accepted", "message": _message_payload(message)}
    raise ManusLocalAdapterError("manus_operation_unsupported")


def run(
    adapter_path: Path,
    argv: list[str],
    *,
    stdin: BinaryIO,
    credential_store: KeyringCredentialStore | None = None,
    client_factory=AgentPost,
) -> dict[str, Any]:
    manifest = _load_manifest(adapter_path)
    if argv not in (["status"], ["request-stdin"]):
        raise ManusLocalAdapterError("manus_operation_unsupported")
    with _client(
        manifest,
        credential_store=credential_store,
        client_factory=client_factory,
    ) as (client, _credential):
        status = _heartbeat(client, _required_text(manifest, "expected_agent_address"))
        if argv == ["status"]:
            return status
        return _run_request(client, _request_payload(stdin))


def main() -> int:
    try:
        result = run(Path(sys.argv[0]).resolve(), sys.argv[1:], stdin=sys.stdin.buffer)
    except ManusLocalAdapterError as exc:
        print(json.dumps({"status": "failed", "error_code": exc.code}, separators=(",", ":")))
        return 1
    except (AgentPostError, ConfigurationError, OSError):
        print(
            json.dumps(
                {"status": "failed", "error_code": "manus_local_request_failed"},
                separators=(",", ":"),
            )
        )
        return 1
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":"), default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
