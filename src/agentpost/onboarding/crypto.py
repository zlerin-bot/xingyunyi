from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from pydantic import SecretStr

DEVICE_CODE_MARKER = "dvc_"
PAIRING_ID_MARKER = "pair_"
CONNECTOR_ID_MARKER = "con_"
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def generate_pairing_id() -> str:
    return f"{PAIRING_ID_MARKER}{secrets.token_urlsafe(18)}"


def generate_connector_id() -> str:
    return f"{CONNECTOR_ID_MARKER}{secrets.token_urlsafe(18)}"


def generate_device_code() -> str:
    return f"{DEVICE_CODE_MARKER}{secrets.token_urlsafe(32)}"


def generate_user_code() -> str:
    raw = "".join(secrets.choice(_CROCKFORD) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


def canonicalize_user_code(value: str) -> str:
    compact = value.strip().upper().replace("-", "").replace(" ", "")
    if len(compact) != 8 or any(character not in _CROCKFORD for character in compact):
        raise ValueError("invalid pairing user code")
    return f"{compact[:4]}-{compact[4:]}"


def pairing_digest(value: str, secret: SecretStr) -> str:
    return hmac.new(
        secret.get_secret_value().encode("utf-8"),
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def derive_agent_api_key(device_code: str, connector_id: str, secret: SecretStr) -> str:
    digest = hmac.new(
        secret.get_secret_value().encode("utf-8"),
        f"agentpost-pairing-v1\0{device_code}\0{connector_id}".encode(),
        hashlib.sha256,
    ).digest()
    encoded = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"agt_{encoded}"
