from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from pydantic import SecretStr

ACCESS_TOKEN_MARKER = "oat_"
REFRESH_TOKEN_MARKER = "ort_"


def _secret_bytes(secret: SecretStr) -> bytes:
    return secret.get_secret_value().encode("utf-8")


def generate_access_token() -> str:
    return f"{ACCESS_TOKEN_MARKER}{secrets.token_urlsafe(32)}"


def generate_refresh_token() -> str:
    return f"{REFRESH_TOKEN_MARKER}{secrets.token_urlsafe(32)}"


def derive_device_access_token(device_code: str, connector_id: str, secret: SecretStr) -> str:
    payload = f"access:{device_code}:{connector_id}".encode()
    digest = hmac.new(_secret_bytes(secret), payload, hashlib.sha256).digest()
    return f"{ACCESS_TOKEN_MARKER}{base64.urlsafe_b64encode(digest).decode().rstrip('=')}"


def derive_device_refresh_token(device_code: str, connector_id: str, secret: SecretStr) -> str:
    payload = f"refresh:{device_code}:{connector_id}".encode()
    digest = hmac.new(_secret_bytes(secret), payload, hashlib.sha256).digest()
    return f"{REFRESH_TOKEN_MARKER}{base64.urlsafe_b64encode(digest).decode().rstrip('=')}"


def digest_oauth_token(raw_token: str, secret: SecretStr) -> str:
    return hmac.new(_secret_bytes(secret), raw_token.encode(), hashlib.sha256).hexdigest()


def token_prefix(raw_token: str) -> str:
    return raw_token[:16]
