from pathlib import Path

import pytest
from pydantic import ValidationError

from agentpost.config import Settings


def test_settings_accept_explicit_values() -> None:
    settings = Settings(
        environment="test",
        database_url="sqlite+pysqlite:///:memory:",
        storage_path=Path("/tmp/agentpost-test"),
        max_attachment_bytes=42,
    )

    assert settings.environment == "test"
    assert settings.max_attachment_bytes == 42
    assert settings.is_production is False


def test_attachment_limit_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        Settings(max_attachment_bytes=0)


def test_production_rejects_development_secrets() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production")


def test_production_requires_registration_token() -> None:
    with pytest.raises(ValidationError, match="REGISTRATION_TOKEN"):
        Settings(
            environment="production",
            api_key_pepper="production-pepper",
            cursor_secret="production-cursor-secret",
        )


def test_production_requires_admin_token() -> None:
    with pytest.raises(ValidationError, match="ADMIN_TOKEN"):
        Settings(
            environment="production",
            api_key_pepper="production-pepper",
            cursor_secret="production-cursor-secret",
            registration_token="registration-secret",
        )


def test_production_accepts_all_required_secrets() -> None:
    settings = Settings(
        environment="production",
        api_key_pepper="production-pepper",
        cursor_secret="production-cursor-secret",
        registration_token="registration-secret",
        admin_token="production-admin-token-at-least-32",
    )

    assert settings.registration_token is not None
    assert settings.admin_token is not None


def test_admin_token_is_optional_but_must_be_strong_when_enabled() -> None:
    assert Settings().admin_token is None
    with pytest.raises(ValidationError, match="ADMIN_TOKEN"):
        Settings(admin_token="too-short")
    with pytest.raises(ValidationError, match="ADMIN_TOKEN"):
        Settings(admin_token="x" * 513)
    settings = Settings(admin_token="admin-token-with-at-least-32-bytes")
    assert settings.admin_token is not None
    assert "admin-token-with-at-least-32-bytes" not in repr(settings)
