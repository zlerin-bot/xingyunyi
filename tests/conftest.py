from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agentpost.config import Settings
from agentpost.db import Database
from agentpost.main import create_app


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    return f"sqlite+pysqlite:///{tmp_path / 'agentpost-test.db'}"


@pytest.fixture
def settings(database_url: str, tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        database_url=database_url,
        storage_path=tmp_path / "attachments",
        api_key_pepper="test-pepper",
        log_level="WARNING",
    )


@pytest.fixture
def database(settings: Settings) -> Iterator[Database]:
    instance = Database(settings.database_url)
    yield instance
    instance.dispose()


@pytest.fixture
def client(settings: Settings, database: Database) -> Iterator[TestClient]:
    app = create_app(settings=settings, database=database)
    with TestClient(app) as test_client:
        yield test_client
