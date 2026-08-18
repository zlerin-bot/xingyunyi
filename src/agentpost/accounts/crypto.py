from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

from cryptography.fernet import Fernet
from pydantic import SecretStr

PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 256
TOTP_PERIOD_SECONDS = 30
TOTP_DIGITS = 6


def validate_password(password: str) -> str:
    if not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
        raise ValueError("password must contain between 12 and 256 characters")
    if password.isspace():
        raise ValueError("password must not contain only whitespace")
    return password


def hash_password(password: str) -> tuple[str, str]:
    validate_password(password)
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=32,
    )
    return base64.urlsafe_b64encode(salt).decode(), derived.hex()


def verify_password(password: str, salt_text: str, expected_hash: str) -> bool:
    if not 1 <= len(password) <= PASSWORD_MAX_LENGTH:
        return False
    try:
        salt = base64.urlsafe_b64decode(salt_text.encode())
    except (ValueError, TypeError):
        return False
    candidate = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=32,
    ).hex()
    return hmac.compare_digest(candidate, expected_hash)


def generate_email_code() -> str:
    return f"{secrets.randbelow(100_000_000):08d}"


def digest_email_code(challenge_id: str, code: str, secret: SecretStr) -> str:
    return hmac.new(
        secret.get_secret_value().encode(),
        f"{challenge_id}.{code}".encode(),
        hashlib.sha256,
    ).hexdigest()


def generate_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _fernet(secret: SecretStr) -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.get_secret_value().encode()).digest())
    return Fernet(key)


def encrypt_application_secret(raw_secret: str, encryption_key: SecretStr) -> str:
    return _fernet(encryption_key).encrypt(raw_secret.encode()).decode()


def decrypt_application_secret(encrypted_secret: str, encryption_key: SecretStr) -> str:
    return _fernet(encryption_key).decrypt(encrypted_secret.encode()).decode()


def encrypt_totp_secret(raw_secret: str, encryption_key: SecretStr) -> str:
    return _fernet(encryption_key).encrypt(raw_secret.encode()).decode()


def decrypt_totp_secret(encrypted_secret: str, encryption_key: SecretStr) -> str:
    return _fernet(encryption_key).decrypt(encrypted_secret.encode()).decode()


def totp_at_step(secret: str, step: int) -> str:
    padded = secret + "=" * ((8 - len(secret) % 8) % 8)
    key = base64.b32decode(padded, casefold=True)
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % (10**TOTP_DIGITS)).zfill(TOTP_DIGITS)


def verify_totp(
    secret: str,
    code: str,
    *,
    now: float | None = None,
    last_used_step: int | None = None,
) -> int | None:
    if len(code) != TOTP_DIGITS or not code.isascii() or not code.isdigit():
        return None
    current_step = int((time.time() if now is None else now) // TOTP_PERIOD_SECONDS)
    for step in (current_step - 1, current_step, current_step + 1):
        if last_used_step is not None and step <= last_used_step:
            continue
        if hmac.compare_digest(totp_at_step(secret, step), code):
            return step
    return None


def totp_uri(secret: str, *, email: str, issuer: str = "Xingyun Relay") -> str:
    label = quote(f"{issuer}:{email}", safe="")
    return (
        f"otpauth://totp/{label}?secret={quote(secret, safe='')}&issuer="
        f"{quote(issuer, safe='')}&algorithm=SHA1&digits={TOTP_DIGITS}&period={TOTP_PERIOD_SECONDS}"
    )


def generate_recovery_codes(count: int = 10) -> list[str]:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return [
        "-".join("".join(secrets.choice(alphabet) for _ in range(5)) for _ in range(2))
        for _ in range(count)
    ]


def digest_recovery_code(code: str, secret: SecretStr) -> str:
    canonical = code.strip().upper()
    return hmac.new(
        secret.get_secret_value().encode(),
        f"recovery.{canonical}".encode(),
        hashlib.sha256,
    ).hexdigest()
