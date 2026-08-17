from __future__ import annotations

import hashlib
import hmac
import secrets

from pydantic import SecretStr

HUMAN_KEY_MARKER = "hum_"
HUMAN_KEY_RANDOM_BYTES = 32
HUMAN_KEY_STORED_PREFIX_LENGTH = 16


def generate_human_key() -> str:
    return f"{HUMAN_KEY_MARKER}{secrets.token_urlsafe(HUMAN_KEY_RANDOM_BYTES)}"


def digest_human_key(raw_key: str, pepper: SecretStr) -> str:
    return hmac.new(
        pepper.get_secret_value().encode("utf-8"),
        raw_key.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def human_key_prefix(raw_key: str) -> str:
    return raw_key[:HUMAN_KEY_STORED_PREFIX_LENGTH]
