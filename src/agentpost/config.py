from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
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
    cursor_secret: SecretStr = SecretStr("development-only-cursor-secret")
    registration_token: SecretStr | None = None
    max_attachment_bytes: int = Field(default=10 * 1024 * 1024, ge=1)

    @property
    def is_production(self) -> bool:
        return self.environment.casefold() == "production"

    @model_validator(mode="after")
    def require_production_secrets(self) -> Settings:
        if not self.is_production:
            return self
        unsafe = {
            "development-only-change-me",
            "development-only-cursor-secret",
        }
        if self.api_key_pepper.get_secret_value() in unsafe:
            raise ValueError("AGENTPOST_API_KEY_PEPPER must be replaced in production")
        if self.cursor_secret.get_secret_value() in unsafe:
            raise ValueError("AGENTPOST_CURSOR_SECRET must be replaced in production")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
