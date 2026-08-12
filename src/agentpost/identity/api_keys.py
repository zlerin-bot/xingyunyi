from __future__ import annotations

import hashlib
import hmac
import secrets

from pydantic import SecretStr

API_KEY_MARKER = "agt_"
API_KEY_RANDOM_BYTES = 32
API_KEY_STORED_PREFIX_LENGTH = 16


def generate_api_key() -> str:
    """Generate an opaque API key with 256 bits of cryptographic entropy."""

    return f"{API_KEY_MARKER}{secrets.token_urlsafe(API_KEY_RANDOM_BYTES)}"


def digest_api_key(api_key: str, pepper: SecretStr) -> str:
    """Create the lookup digest stored in the database; never store the raw key."""

    return hmac.new(
        pepper.get_secret_value().encode("utf-8"),
        api_key.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def api_key_prefix(api_key: str) -> str:
    return api_key[:API_KEY_STORED_PREFIX_LENGTH]
