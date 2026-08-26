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
        codex_setup_platforms="mac,LINUX,mac",
        workbuddy_setup_platforms="MAC",
        doubao_work_setup_platforms="MAC,windows",
        openclaw_setup_platforms="linux,MAC,linux",
        hermes_setup_platforms="linux,WINDOWS,linux",
        connector_release_version="0.1.1",
        connector_wheel_url=("https://agentpost.me/downloads/agentpost-0.1.1-py3-none-any.whl"),
        connector_wheel_sha256="A" * 64,
    )

    assert settings.managed_agent_domain == "agentpost.me"
    assert settings.public_base_url == "https://agentpost.me"
    assert settings.codex_setup_platforms == "mac,linux"
    assert settings.enabled_codex_setup_platforms == ("mac", "linux")
    assert settings.enabled_host_setup_platforms == {
        "codex": ("mac", "linux"),
        "workbuddy": ("mac",),
        "doubao_work": ("mac", "windows"),
        "openclaw": ("linux", "mac"),
        "hermes": ("linux", "windows"),
    }
    assert settings.enabled_host_connection_modes == {
        "workbuddy": "local_bootstrap",
        "doubao_work": "local_bootstrap",
        "openclaw": "local_bootstrap",
        "hermes": "local_bootstrap",
        "codex": "local_bootstrap",
        "manus": "unavailable",
    }
    assert settings.connector_release_version == "0.1.1"
    assert settings.connector_wheel_sha256 == "a" * 64
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
    with pytest.raises(ValidationError, match="only mac, windows, or linux"):
        Settings(openclaw_setup_platforms="linux,android")
    with pytest.raises(ValidationError, match="release 0.1.1"):
        Settings(codex_setup_platforms="mac")


def test_host_setup_platforms_fall_back_to_codex_policy_for_compatibility() -> None:
    settings = Settings(
        codex_setup_platforms="mac",
        connector_release_version="0.1.1",
        connector_wheel_url="https://agentpost.me/downloads/agentpost-0.1.1-py3-none-any.whl",
    )

    assert settings.enabled_host_setup_platforms == {
        "codex": ("mac",),
        "workbuddy": ("mac",),
        "doubao_work": (),
        "openclaw": ("mac",),
        "hermes": (),
    }
    with pytest.raises(ValidationError, match="safe HTTPS wheel URL"):
        Settings(connector_wheel_url="https://agentpost.me/downloads/pkg.whl';touch x")
    with pytest.raises(ValidationError, match="64 hexadecimal"):
        Settings(connector_wheel_sha256="not-a-digest")
    with pytest.raises(ValidationError, match="configured release version"):
        Settings(
            connector_release_version="0.1.1",
            connector_wheel_url=("https://agentpost.me/downloads/agentpost-0.1.0-py3-none-any.whl"),
        )


def test_manus_connection_mode_requires_remote_mcp_oauth() -> None:
    settings = Settings(remote_mcp_oauth_enabled=True)

    assert settings.enabled_host_connection_modes["manus"] == "remote_mcp_oauth"


def test_doubao_work_connection_mode_requires_its_gate_and_remote_mcp_oauth() -> None:
    settings = Settings(
        remote_mcp_oauth_enabled=True,
        doubao_work_remote_mcp_enabled=True,
    )

    assert settings.enabled_host_connection_modes["doubao_work"] == "remote_mcp_oauth"
    with pytest.raises(ValidationError, match="Remote MCP"):
        Settings(doubao_work_remote_mcp_enabled=True)

    local = Settings(
        remote_mcp_oauth_enabled=True,
        doubao_work_remote_mcp_enabled=True,
        doubao_work_setup_platforms="mac",
        connector_release_version="0.1.1",
        connector_wheel_url="https://agentpost.me/downloads/agentpost-0.1.1-py3-none-any.whl",
    )
    assert local.enabled_host_connection_modes["doubao_work"] == "local_bootstrap"


def test_remote_mcp_resource_allows_one_opaque_connect_path() -> None:
    resource = "https://agentpost.example/mcp/connect/probe-opaque-intent-1234567890"
    assert Settings(remote_mcp_resource_url=resource).remote_mcp_resource_url == resource
    with pytest.raises(ValidationError, match="opaque"):
        Settings(remote_mcp_resource_url="https://agentpost.example/mcp/connect/too-short")
    with pytest.raises(ValidationError, match="opaque"):
        Settings(
            remote_mcp_resource_url=(
                "https://agentpost.example/mcp/connect/probe-opaque-intent-1234567890/extra"
            )
        )
    with pytest.raises(ValidationError, match="opaque"):
        Settings(
            remote_mcp_resource_url=(
                "https://agentpost.example/mcp/connect/"
                "probe-opaque-intent-1234567890?secret=not-allowed"
            )
        )


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
            rate_limit_secret="production-rate-limit-secret",
            pairing_enabled=False,
        )


def test_production_requires_admin_token() -> None:
    with pytest.raises(ValidationError, match="ADMIN_TOKEN"):
        Settings(
            environment="production",
            api_key_pepper="production-pepper",
            human_api_key_pepper="production-human-pepper",
            cursor_secret="production-cursor-secret",
            rate_limit_secret="production-rate-limit-secret",
            pairing_enabled=False,
            registration_token="registration-secret",
        )


def test_production_accepts_all_required_secrets() -> None:
    settings = Settings(
        environment="production",
        api_key_pepper="production-pepper",
        human_api_key_pepper="production-human-pepper",
        cursor_secret="production-cursor-secret",
        rate_limit_secret="production-rate-limit-secret",
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
        "rate_limit_secret": "production-rate-limit-secret",
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
            rate_limit_secret="production-rate-limit-secret",
            pairing_enabled=False,
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


def test_open_registration_requires_human_self_service() -> None:
    with pytest.raises(ValidationError, match="HUMAN_SELF_SERVICE_ENABLED"):
        Settings(open_registration_enabled=True)


def test_enterprise_oidc_requires_human_service_and_canonical_allowlist() -> None:
    with pytest.raises(ValidationError, match="HUMAN_SELF_SERVICE_ENABLED"):
        Settings(enterprise_oidc_enabled=True, oidc_allowed_issuers="https://idp.example")
    settings = Settings(
        human_self_service_enabled=True,
        enterprise_oidc_enabled=True,
        oidc_allowed_issuers=" https://idp.example/,https://idp.example ",
    )
    assert settings.allowed_oidc_issuers == frozenset({"https://idp.example"})
    with pytest.raises(ValidationError, match="OIDC_ALLOWED_ISSUERS"):
        Settings(oidc_allowed_issuers="https://user:secret@idp.example")


def test_production_human_self_service_requires_https_smtp_and_secrets() -> None:
    base = {
        "environment": "production",
        "api_key_pepper": "production-pepper",
        "human_api_key_pepper": "production-human-pepper",
        "cursor_secret": "production-cursor-secret",
        "rate_limit_secret": "production-rate-limit-secret",
        "pairing_secret": "production-pairing-secret",
        "registration_token": "registration-secret",
        "admin_token": "production-admin-token-at-least-32",
        "managed_agent_domain": "agentpost.me",
        "public_base_url": "https://agentpost.me",
        "human_self_service_enabled": True,
        "open_registration_enabled": True,
    }
    with pytest.raises(ValidationError, match="HUMAN_AUTH_SECRET"):
        Settings(**base)

    with pytest.raises(ValidationError, match="EMAIL_DELIVERY_MODE"):
        Settings(
            **base,
            human_auth_secret="production-human-auth-secret",
            human_mfa_encryption_key="production-human-mfa-key",
        )

    with pytest.raises(ValidationError, match="Encrypted SMTP"):
        Settings(
            **base,
            human_auth_secret="production-human-auth-secret",
            human_mfa_encryption_key="production-human-mfa-key",
            email_delivery_mode="smtp",
            smtp_host="smtp.example.com",
            smtp_from_address="no-reply@agentpost.me",
            smtp_starttls=False,
        )

    with pytest.raises(ValidationError, match="mutually exclusive"):
        Settings(smtp_starttls=True, smtp_ssl=True)

    with pytest.raises(ValidationError, match="SMTP_PASSWORD"):
        Settings(smtp_username="mailer")

    configured = Settings(
        **base,
        human_auth_secret="production-human-auth-secret",
        human_mfa_encryption_key="production-human-mfa-key",
        email_delivery_mode="smtp",
        smtp_host="smtp.example.com",
        smtp_from_address="no-reply@agentpost.me",
    )
    assert configured.human_self_service_enabled is True
    assert configured.open_registration_enabled is True
    assert "production-human-auth-secret" not in repr(configured)


def test_production_rate_limiting_requires_an_independent_secret() -> None:
    with pytest.raises(ValidationError, match="RATE_LIMIT_SECRET"):
        Settings(
            environment="production",
            api_key_pepper="production-pepper",
            human_api_key_pepper="production-human-pepper",
            cursor_secret="production-cursor-secret",
            registration_token="registration-secret",
            admin_token="production-admin-token-at-least-32",
        )
    disabled = Settings(
        environment="production",
        api_key_pepper="production-pepper",
        human_api_key_pepper="production-human-pepper",
        cursor_secret="production-cursor-secret",
        registration_token="registration-secret",
        admin_token="production-admin-token-at-least-32",
        rate_limit_enabled=False,
        pairing_enabled=False,
    )
    assert disabled.rate_limit_enabled is False
