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
    registration_token: SecretStr | None = None
    admin_token: SecretStr | None = None
    pairing_enabled: bool = True
    managed_agent_domain: str = "agents.local"
    public_base_url: str = "http://127.0.0.1:8000"
    pairing_ttl_seconds: int = Field(default=10 * 60, ge=5 * 60, le=15 * 60)
    pairing_poll_interval_seconds: int = Field(default=5, ge=3, le=30)
    max_attachment_bytes: int = Field(default=10 * 1024 * 1024, ge=1)
    human_session_ttl_seconds: int = Field(default=12 * 60 * 60, ge=300, le=7 * 24 * 60 * 60)
    human_confirmation_ttl_seconds: int = Field(default=5 * 60, ge=60, le=15 * 60)
    approval_default_ttl_seconds: int = Field(
        default=24 * 60 * 60,
        ge=5 * 60,
        le=7 * 24 * 60 * 60,
    )

    @field_validator("registration_token", "admin_token", mode="before")
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
        if not self.is_production:
            return self
        unsafe = {
            "development-only-change-me",
            "development-only-human-key-pepper",
            "development-only-cursor-secret",
            "development-only-pairing-secret",
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
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
