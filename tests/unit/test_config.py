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
