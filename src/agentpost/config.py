from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables or an optional .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="AGENTPOST_",
        extra="ignore",
        case_sensitive=False,
    )

    environment: str = "development"
    database_url: str = "postgresql+psycopg://agentpost:agentpost@localhost:5432/agentpost"
    storage_path: Path = Path("data/attachments")
    log_level: str = "INFO"
    api_key_pepper: SecretStr = SecretStr("development-only-change-me")
    human_api_key_pepper: SecretStr = SecretStr("development-only-human-key-pepper")
    cursor_secret: SecretStr = SecretStr("development-only-cursor-secret")
    pairing_secret: SecretStr = SecretStr("development-only-pairing-secret")
    human_auth_secret: SecretStr = SecretStr("development-only-human-auth-secret")
    human_mfa_encryption_key: SecretStr = SecretStr("development-only-human-mfa-encryption-key")
    oauth_token_pepper: SecretStr = SecretStr("development-only-oauth-token-pepper")
    rate_limit_secret: SecretStr = SecretStr("development-only-rate-limit-secret")
    registration_token: SecretStr | None = None
    admin_token: SecretStr | None = None
    pairing_enabled: bool = True
    human_self_service_enabled: bool = False
    open_registration_enabled: bool = False
    remote_mcp_oauth_enabled: bool = False
    enterprise_oidc_enabled: bool = False
    codex_setup_platforms: str = ""
    workbuddy_setup_platforms: str = ""
    openclaw_setup_platforms: str = ""
    connector_release_version: str = "0.1.0"
    connector_wheel_url: str = "https://agentpost.me/downloads/agentpost-0.1.0-py3-none-any.whl"
    connector_wheel_sha256: str = "1fc3f42e8c1141ce65481778587544fc9bf441438c852c0332594ab24a75fdf7"
    rate_limit_enabled: bool = True
    oidc_allowed_issuers: str = ""
    email_delivery_mode: str = "test"
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from_address: str | None = None
    smtp_starttls: bool = True
    smtp_ssl: bool = False
    managed_agent_domain: str = "agents.local"
    public_base_url: str = "http://127.0.0.1:8000"
    remote_mcp_resource_url: str | None = None
    pairing_ttl_seconds: int = Field(default=10 * 60, ge=5 * 60, le=15 * 60)
    pairing_poll_interval_seconds: int = Field(default=5, ge=3, le=30)
    email_challenge_ttl_seconds: int = Field(default=10 * 60, ge=5 * 60, le=30 * 60)
    email_challenge_cooldown_seconds: int = Field(default=60, ge=10, le=10 * 60)
    email_challenge_max_attempts: int = Field(default=5, ge=3, le=10)
    email_challenge_ip_limit: int = Field(default=20, ge=1, le=1000)
    email_challenge_address_limit: int = Field(default=5, ge=1, le=100)
    email_challenge_rate_window_seconds: int = Field(default=60 * 60, ge=60, le=24 * 60 * 60)
    human_login_ip_limit: int = Field(default=60, ge=1, le=5000)
    human_login_account_limit: int = Field(default=10, ge=1, le=1000)
    human_login_rate_window_seconds: int = Field(default=15 * 60, ge=60, le=24 * 60 * 60)
    pairing_create_ip_limit: int = Field(default=30, ge=1, le=5000)
    pairing_poll_ip_limit: int = Field(default=1200, ge=1, le=10000)
    pairing_rate_window_seconds: int = Field(default=60 * 60, ge=60, le=24 * 60 * 60)
    domain_verification_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    connector_heartbeat_interval_seconds: int = Field(default=30, ge=10, le=5 * 60)
    oauth_access_token_ttl_seconds: int = Field(default=60 * 60, ge=5 * 60, le=24 * 60 * 60)
    oauth_refresh_token_ttl_seconds: int = Field(
        default=30 * 24 * 60 * 60, ge=24 * 60 * 60, le=180 * 24 * 60 * 60
    )
    oidc_state_ttl_seconds: int = Field(default=10 * 60, ge=5 * 60, le=15 * 60)
    oidc_http_timeout_seconds: float = Field(default=10.0, gt=0, le=30)
    max_attachment_bytes: int = Field(default=10 * 1024 * 1024, ge=1)
    human_session_ttl_seconds: int = Field(default=12 * 60 * 60, ge=300, le=7 * 24 * 60 * 60)
    human_confirmation_ttl_seconds: int = Field(default=5 * 60, ge=60, le=15 * 60)
    approval_default_ttl_seconds: int = Field(
        default=24 * 60 * 60,
        ge=5 * 60,
        le=7 * 24 * 60 * 60,
    )

    @field_validator(
        "registration_token",
        "admin_token",
        "smtp_password",
        mode="before",
    )
    @classmethod
    def empty_registration_token_is_unset(cls, value: object) -> object:
        if isinstance(value, SecretStr):
            return value if value.get_secret_value().strip() else None
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("admin_token")
    @classmethod
    def admin_token_is_strong_when_enabled(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and not 32 <= len(value.get_secret_value()) <= 512:
            raise ValueError("AGENTPOST_ADMIN_TOKEN must contain between 32 and 512 characters")
        return value

    @field_validator("email_delivery_mode")
    @classmethod
    def email_delivery_mode_is_supported(cls, value: str) -> str:
        canonical = value.strip().casefold()
        if canonical not in {"test", "smtp"}:
            raise ValueError("AGENTPOST_EMAIL_DELIVERY_MODE must be test or smtp")
        return canonical

    @field_validator(
        "codex_setup_platforms",
        "workbuddy_setup_platforms",
        "openclaw_setup_platforms",
    )
    @classmethod
    def setup_platforms_are_supported(cls, value: str) -> str:
        supported = {"mac", "windows", "linux"}
        canonical = [item.strip().casefold() for item in value.split(",") if item.strip()]
        if any(item not in supported for item in canonical):
            raise ValueError("Agent setup platforms may contain only mac, windows, or linux")
        return ",".join(dict.fromkeys(canonical))

    @field_validator("connector_release_version")
    @classmethod
    def connector_release_version_is_supported(cls, value: str) -> str:
        canonical = value.strip()
        if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", canonical):
            raise ValueError("AGENTPOST_CONNECTOR_RELEASE_VERSION must use major.minor.patch")
        return canonical

    @field_validator("connector_wheel_url")
    @classmethod
    def connector_wheel_url_is_safe(cls, value: str) -> str:
        cleaned = value.strip()
        if not re.fullmatch(
            r"https://[A-Za-z0-9.-]+(?::[0-9]{1,5})?/[A-Za-z0-9._~/-]+\.whl",
            cleaned,
        ):
            raise ValueError("AGENTPOST_CONNECTOR_WHEEL_URL must be a safe HTTPS wheel URL")
        return cleaned

    @field_validator("connector_wheel_sha256")
    @classmethod
    def connector_wheel_sha256_is_valid(cls, value: str) -> str:
        canonical = value.strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", canonical):
            raise ValueError("AGENTPOST_CONNECTOR_WHEEL_SHA256 must be 64 hexadecimal characters")
        return canonical

    @field_validator("managed_agent_domain")
    @classmethod
    def managed_domain_is_canonical(cls, value: str) -> str:
        canonical = value.strip().lower()
        if not canonical or len(canonical) > 255:
            raise ValueError("AGENTPOST_MANAGED_AGENT_DOMAIN must be a DNS-style domain")
        labels = canonical.split(".")
        if any(
            not label
            or len(label) > 63
            or not label[0].isalnum()
            or not label[-1].isalnum()
            or any(
                not (character.isascii() and (character.isalnum() or character == "-"))
                for character in label
            )
            for label in labels
        ):
            raise ValueError("AGENTPOST_MANAGED_AGENT_DOMAIN must be a DNS-style domain")
        return canonical

    @field_validator("public_base_url")
    @classmethod
    def public_base_url_is_an_origin(cls, value: str) -> str:
        cleaned = value.strip().rstrip("/")
        parsed = urlsplit(cleaned)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("AGENTPOST_PUBLIC_BASE_URL must be an HTTP(S) origin")
        return cleaned

    @field_validator("remote_mcp_resource_url")
    @classmethod
    def remote_mcp_resource_is_url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        cleaned = value.strip().rstrip("/")
        parsed = urlsplit(cleaned)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path != "/mcp"
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("AGENTPOST_REMOTE_MCP_RESOURCE_URL must end with /mcp")
        return cleaned

    @field_validator("oidc_allowed_issuers")
    @classmethod
    def oidc_issuers_are_origins_or_paths(cls, value: str) -> str:
        canonical: list[str] = []
        for raw in value.split(","):
            cleaned = raw.strip().rstrip("/")
            if not cleaned:
                continue
            parsed = urlsplit(cleaned)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("AGENTPOST_OIDC_ALLOWED_ISSUERS contains an invalid issuer")
            canonical.append(cleaned)
        return ",".join(dict.fromkeys(canonical))

    @property
    def allowed_oidc_issuers(self) -> frozenset[str]:
        return frozenset(item for item in self.oidc_allowed_issuers.split(",") if item)

    @property
    def enabled_codex_setup_platforms(self) -> tuple[str, ...]:
        return tuple(item for item in self.codex_setup_platforms.split(",") if item)

    @property
    def enabled_host_setup_platforms(self) -> dict[str, tuple[str, ...]]:
        codex = self.enabled_codex_setup_platforms
        workbuddy = tuple(item for item in self.workbuddy_setup_platforms.split(",") if item)
        openclaw = tuple(item for item in self.openclaw_setup_platforms.split(",") if item)
        return {
            "codex": codex,
            # Empty host-specific settings preserve the pre-0.1.10 release policy.
            "workbuddy": workbuddy or codex,
            "openclaw": openclaw or codex,
        }

    @property
    def is_production(self) -> bool:
        return self.environment.casefold() == "production"

    @model_validator(mode="after")
    def connector_release_is_consistent(self) -> Settings:
        expected_filename = f"agentpost-{self.connector_release_version}-"
        if expected_filename not in self.connector_wheel_url.rsplit("/", maxsplit=1)[-1]:
            raise ValueError(
                "AGENTPOST_CONNECTOR_WHEEL_URL must contain the configured release version"
            )
        setup_is_enabled = any(self.enabled_host_setup_platforms.values())
        if setup_is_enabled:
            version = tuple(int(part) for part in self.connector_release_version.split("."))
            if version < (0, 1, 1):
                raise ValueError("Agent setup platforms require Connector release 0.1.1 or newer")
        if self.is_production and setup_is_enabled:
            release_origin = urlsplit(self.connector_wheel_url)
            public_origin = urlsplit(self.public_base_url)
            if (release_origin.scheme, release_origin.netloc) != (
                public_origin.scheme,
                public_origin.netloc,
            ):
                raise ValueError(
                    "AGENTPOST_CONNECTOR_WHEEL_URL must use the production public origin"
                )
        return self

    @model_validator(mode="after")
    def require_production_secrets(self) -> Settings:
        if self.smtp_ssl and self.smtp_starttls:
            raise ValueError(
                "AGENTPOST_SMTP_SSL and AGENTPOST_SMTP_STARTTLS are mutually exclusive"
            )
        if self.smtp_username and self.smtp_password is None:
            raise ValueError("AGENTPOST_SMTP_PASSWORD is required when SMTP username is configured")
        if self.smtp_password is not None and not self.smtp_username:
            raise ValueError("AGENTPOST_SMTP_USERNAME is required when SMTP password is configured")
        if self.open_registration_enabled and not self.human_self_service_enabled:
            raise ValueError(
                "AGENTPOST_HUMAN_SELF_SERVICE_ENABLED must be true when open "
                "registration is enabled"
            )
        if self.enterprise_oidc_enabled:
            if not self.human_self_service_enabled:
                raise ValueError(
                    "AGENTPOST_HUMAN_SELF_SERVICE_ENABLED must be true when "
                    "enterprise OIDC is enabled"
                )
            if not self.allowed_oidc_issuers:
                raise ValueError(
                    "AGENTPOST_OIDC_ALLOWED_ISSUERS is required when enterprise OIDC is enabled"
                )
        if not self.is_production:
            return self
        unsafe = {
            "development-only-change-me",
            "development-only-human-key-pepper",
            "development-only-cursor-secret",
            "development-only-pairing-secret",
            "development-only-human-auth-secret",
            "development-only-human-mfa-encryption-key",
            "development-only-oauth-token-pepper",
            "development-only-rate-limit-secret",
        }
        if self.api_key_pepper.get_secret_value() in unsafe:
            raise ValueError("AGENTPOST_API_KEY_PEPPER must be replaced in production")
        if self.cursor_secret.get_secret_value() in unsafe:
            raise ValueError("AGENTPOST_CURSOR_SECRET must be replaced in production")
        if self.rate_limit_enabled and self.rate_limit_secret.get_secret_value() in unsafe:
            raise ValueError("AGENTPOST_RATE_LIMIT_SECRET must be replaced in production")
        if self.human_api_key_pepper.get_secret_value() in unsafe:
            raise ValueError("AGENTPOST_HUMAN_API_KEY_PEPPER must be replaced in production")
        if self.registration_token is None:
            raise ValueError("AGENTPOST_REGISTRATION_TOKEN must be configured in production")
        if self.admin_token is None:
            raise ValueError("AGENTPOST_ADMIN_TOKEN must be configured in production")
        if self.pairing_enabled:
            if self.pairing_secret.get_secret_value() in unsafe:
                raise ValueError("AGENTPOST_PAIRING_SECRET must be replaced in production")
            if not self.public_base_url.startswith("https://"):
                raise ValueError("AGENTPOST_PUBLIC_BASE_URL must use HTTPS when pairing is enabled")
        if self.human_self_service_enabled:
            if self.human_auth_secret.get_secret_value() in unsafe:
                raise ValueError("AGENTPOST_HUMAN_AUTH_SECRET must be replaced in production")
            if self.human_mfa_encryption_key.get_secret_value() in unsafe:
                raise ValueError(
                    "AGENTPOST_HUMAN_MFA_ENCRYPTION_KEY must be replaced in production"
                )
            if not self.public_base_url.startswith("https://"):
                raise ValueError(
                    "AGENTPOST_PUBLIC_BASE_URL must use HTTPS when Human self-service is enabled"
                )
            if self.email_delivery_mode != "smtp":
                raise ValueError(
                    "AGENTPOST_EMAIL_DELIVERY_MODE must be smtp when Human self-service is enabled"
                )
            if not self.smtp_host or not self.smtp_from_address:
                raise ValueError(
                    "SMTP host and from address are required when Human self-service is enabled"
                )
            if not (self.smtp_starttls or self.smtp_ssl):
                raise ValueError("Encrypted SMTP is required when Human self-service is enabled")
        if self.remote_mcp_oauth_enabled:
            if self.oauth_token_pepper.get_secret_value() in unsafe:
                raise ValueError("AGENTPOST_OAUTH_TOKEN_PEPPER must be replaced in production")
            if not self.public_base_url.startswith("https://"):
                raise ValueError(
                    "AGENTPOST_PUBLIC_BASE_URL must use HTTPS when Remote MCP OAuth is enabled"
                )
            if self.remote_mcp_resource_url is not None and not (
                self.remote_mcp_resource_url.startswith("https://")
            ):
                raise ValueError("AGENTPOST_REMOTE_MCP_RESOURCE_URL must use HTTPS in production")
        if self.enterprise_oidc_enabled:
            if any(not issuer.startswith("https://") for issuer in self.allowed_oidc_issuers):
                raise ValueError("OIDC issuers must use HTTPS in production")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
