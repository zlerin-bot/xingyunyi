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


def test_human_session_ttl_is_bounded() -> None:
    assert Settings().human_session_ttl_seconds == 43_200
    with pytest.raises(ValidationError):
        Settings(human_session_ttl_seconds=299)
    with pytest.raises(ValidationError):
        Settings(human_session_ttl_seconds=7 * 24 * 60 * 60 + 1)


def test_human_confirmation_ttl_is_short_and_bounded() -> None:
    assert Settings().human_confirmation_ttl_seconds == 300
    with pytest.raises(ValidationError):
        Settings(human_confirmation_ttl_seconds=59)
    with pytest.raises(ValidationError):
        Settings(human_confirmation_ttl_seconds=901)


def test_approval_default_ttl_is_bounded() -> None:
    assert Settings().approval_default_ttl_seconds == 86_400
    with pytest.raises(ValidationError):
        Settings(approval_default_ttl_seconds=299)
    with pytest.raises(ValidationError):
        Settings(approval_default_ttl_seconds=7 * 24 * 60 * 60 + 1)


def test_pairing_configuration_is_bounded_and_canonical() -> None:
    settings = Settings(
        managed_agent_domain="AgentPost.Me",
        public_base_url="https://agentpost.me/",
    )

    assert settings.managed_agent_domain == "agentpost.me"
    assert settings.public_base_url == "https://agentpost.me"
    assert settings.pairing_ttl_seconds == 600
    assert settings.pairing_poll_interval_seconds == 5
    with pytest.raises(ValidationError):
        Settings(managed_agent_domain="not_a_domain!")
    with pytest.raises(ValidationError):
        Settings(public_base_url="https://user:secret@agentpost.me")
    with pytest.raises(ValidationError):
        Settings(pairing_ttl_seconds=299)
    with pytest.raises(ValidationError):
        Settings(pairing_poll_interval_seconds=2)


def test_production_rejects_development_secrets() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production")


def test_production_requires_registration_token() -> None:
    with pytest.raises(ValidationError, match="REGISTRATION_TOKEN"):
        Settings(
            environment="production",
            api_key_pepper="production-pepper",
            human_api_key_pepper="production-human-pepper",
            cursor_secret="production-cursor-secret",
        )


def test_production_requires_admin_token() -> None:
    with pytest.raises(ValidationError, match="ADMIN_TOKEN"):
        Settings(
            environment="production",
            api_key_pepper="production-pepper",
            human_api_key_pepper="production-human-pepper",
            cursor_secret="production-cursor-secret",
            registration_token="registration-secret",
        )


def test_production_accepts_all_required_secrets() -> None:
    settings = Settings(
        environment="production",
        api_key_pepper="production-pepper",
        human_api_key_pepper="production-human-pepper",
        cursor_secret="production-cursor-secret",
        pairing_secret="production-pairing-secret",
        registration_token="registration-secret",
        admin_token="production-admin-token-at-least-32",
        managed_agent_domain="agentpost.me",
        public_base_url="https://agentpost.me",
    )

    assert settings.registration_token is not None
    assert settings.admin_token is not None


def test_production_pairing_requires_separate_secret_and_https() -> None:
    base = {
        "environment": "production",
        "api_key_pepper": "production-pepper",
        "human_api_key_pepper": "production-human-pepper",
        "cursor_secret": "production-cursor-secret",
        "registration_token": "registration-secret",
        "admin_token": "production-admin-token-at-least-32",
        "managed_agent_domain": "agentpost.me",
    }
    with pytest.raises(ValidationError, match="PAIRING_SECRET"):
        Settings(**base)
    with pytest.raises(ValidationError, match="PUBLIC_BASE_URL"):
        Settings(
            **base,
            pairing_secret="production-pairing-secret",
            public_base_url="http://203.0.113.10",
        )

    disabled = Settings(**base, pairing_enabled=False)
    assert disabled.pairing_enabled is False


def test_production_requires_a_separate_human_key_pepper() -> None:
    with pytest.raises(ValidationError, match="HUMAN_API_KEY_PEPPER"):
        Settings(
            environment="production",
            api_key_pepper="production-pepper",
            cursor_secret="production-cursor-secret",
            registration_token="registration-secret",
            admin_token="production-admin-token-at-least-32",
        )


def test_admin_token_is_optional_but_must_be_strong_when_enabled() -> None:
    assert Settings().admin_token is None
    with pytest.raises(ValidationError, match="ADMIN_TOKEN"):
        Settings(admin_token="too-short")
    with pytest.raises(ValidationError, match="ADMIN_TOKEN"):
        Settings(admin_token="x" * 513)
    settings = Settings(admin_token="admin-token-with-at-least-32-bytes")
    assert settings.admin_token is not None
    assert "admin-token-with-at-least-32-bytes" not in repr(settings)
