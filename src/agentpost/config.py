from __future__ import annotations

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
    registration_token: SecretStr | None = None
    admin_token: SecretStr | None = None
    pairing_enabled: bool = True
    human_self_service_enabled: bool = False
    open_registration_enabled: bool = False
    email_delivery_mode: str = "test"
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from_address: str | None = None
    smtp_starttls: bool = True
    managed_agent_domain: str = "agents.local"
    public_base_url: str = "http://127.0.0.1:8000"
    pairing_ttl_seconds: int = Field(default=10 * 60, ge=5 * 60, le=15 * 60)
    pairing_poll_interval_seconds: int = Field(default=5, ge=3, le=30)
    email_challenge_ttl_seconds: int = Field(default=10 * 60, ge=5 * 60, le=30 * 60)
    email_challenge_cooldown_seconds: int = Field(default=60, ge=10, le=10 * 60)
    email_challenge_max_attempts: int = Field(default=5, ge=3, le=10)
    domain_verification_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    connector_heartbeat_interval_seconds: int = Field(default=30, ge=10, le=5 * 60)
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

    @property
    def is_production(self) -> bool:
        return self.environment.casefold() == "production"

    @model_validator(mode="after")
    def require_production_secrets(self) -> Settings:
        if self.open_registration_enabled and not self.human_self_service_enabled:
            raise ValueError(
                "AGENTPOST_HUMAN_SELF_SERVICE_ENABLED must be true when open "
                "registration is enabled"
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
        }
        if self.api_key_pepper.get_secret_value() in unsafe:
            raise ValueError("AGENTPOST_API_KEY_PEPPER must be replaced in production")
        if self.cursor_secret.get_secret_value() in unsafe:
            raise ValueError("AGENTPOST_CURSOR_SECRET must be replaced in production")
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
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
