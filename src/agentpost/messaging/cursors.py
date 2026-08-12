from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import SecretStr


class InvalidCursorError(ValueError):
    pass


@dataclass(frozen=True)
class InboxCursor:
    agent_id: UUID
    filter_hash: str
    inbox_seq: int


def normalized_filter_hash(filters: dict[str, Any]) -> str:
    canonical = json.dumps(filters, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("ascii")).hexdigest()


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    try:
        return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    except (ValueError, TypeError) as exc:
        raise InvalidCursorError("cursor is malformed") from exc


def encode_cursor(cursor: InboxCursor, secret: SecretStr) -> str:
    payload = json.dumps(
        {
            "v": 1,
            "agent_id": str(cursor.agent_id),
            "filter_hash": cursor.filter_hash,
            "inbox_seq": cursor.inbox_seq,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    signature = hmac.new(
        secret.get_secret_value().encode("utf-8"), payload, hashlib.sha256
    ).digest()
    return f"{_encode(payload)}.{_encode(signature)}"


def decode_cursor(
    token: str,
    *,
    secret: SecretStr,
    expected_agent_id: UUID,
    expected_filter_hash: str,
) -> InboxCursor:
    if not token or len(token) > 2048 or token.count(".") != 1:
        raise InvalidCursorError("cursor is malformed")
    encoded_payload, encoded_signature = token.split(".", maxsplit=1)
    payload = _decode(encoded_payload)
    signature = _decode(encoded_signature)
    expected_signature = hmac.new(
        secret.get_secret_value().encode("utf-8"), payload, hashlib.sha256
    ).digest()
    if not hmac.compare_digest(signature, expected_signature):
        raise InvalidCursorError("cursor signature is invalid")

    try:
        data = json.loads(payload)
        cursor = InboxCursor(
            agent_id=UUID(data["agent_id"]),
            filter_hash=str(data["filter_hash"]),
            inbox_seq=int(data["inbox_seq"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise InvalidCursorError("cursor payload is invalid") from exc
    if data.get("v") != 1 or cursor.inbox_seq < 0:
        raise InvalidCursorError("cursor version or sequence is invalid")
    if cursor.agent_id != expected_agent_id:
        raise InvalidCursorError("cursor belongs to a different agent")
    if not hmac.compare_digest(cursor.filter_hash, expected_filter_hash):
        raise InvalidCursorError("cursor is incompatible with these filters")
    return cursor
