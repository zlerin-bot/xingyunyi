from __future__ import annotations

import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from agentpost.db import Database

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_SAFE_DATABASE_NAME = re.compile(r"^agentpost_test(?:_[a-z0-9_]+)?$")
_ADVISORY_LOCK_ID = 6_149_103_710


def pytest_configure() -> None:
    """Reject an explicitly unsafe URL once, before any fixture can connect."""

    if os.getenv("AGENTPOST_TEST_POSTGRES_URL", "").strip():
        _validated_postgres_url()


def _validated_postgres_url() -> str:
    raw = os.getenv("AGENTPOST_TEST_POSTGRES_URL", "").strip()
    if not raw:
        pytest.skip(
            "AGENTPOST_TEST_POSTGRES_URL is unset; PostgreSQL acceptance tests are opt-in",
            allow_module_level=False,
        )
    try:
        parsed = make_url(raw)
    except ArgumentError as exc:
        raise pytest.UsageError(
            "AGENTPOST_TEST_POSTGRES_URL is not a valid SQLAlchemy URL"
        ) from exc

    if parsed.get_backend_name() != "postgresql":
        raise pytest.UsageError("AGENTPOST_TEST_POSTGRES_URL must use PostgreSQL")
    database_name = (parsed.database or "").casefold()
    if not _SAFE_DATABASE_NAME.fullmatch(database_name):
        raise pytest.UsageError(
            "refusing destructive PostgreSQL acceptance tests: database name must be "
            "agentpost_test or start with agentpost_test_"
        )
    if os.getenv("PYTEST_XDIST_WORKER"):
        raise pytest.UsageError(
            "tests/postgres must run without pytest-xdist unless each worker has its own "
            "validated database"
        )
    return raw


def _alembic_config(url: str) -> Config:
    config = Config(str(REPOSITORY_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPOSITORY_ROOT / "migrations"))
    config.set_main_option("prepend_sys_path", str(REPOSITORY_ROOT / "src"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


@contextmanager
def _migration_environment(url: str) -> Iterator[None]:
    """Prevent migrations/env.py from honoring an unrelated process database URL."""

    previous = os.environ.get("AGENTPOST_DATABASE_URL")
    os.environ["AGENTPOST_DATABASE_URL"] = url
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("AGENTPOST_DATABASE_URL", None)
        else:
            os.environ["AGENTPOST_DATABASE_URL"] = previous


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    url = _validated_postgres_url()
    guard_engine = create_engine(url, pool_pre_ping=True)
    with guard_engine.connect() as connection:
        actual_database = connection.scalar(text("SELECT current_database()"))
        if not isinstance(actual_database, str) or not _SAFE_DATABASE_NAME.fullmatch(
            actual_database.casefold()
        ):
            raise pytest.UsageError(
                "server resolved AGENTPOST_TEST_POSTGRES_URL to a non-test database; refusing"
            )
        locked = connection.scalar(
            text("SELECT pg_try_advisory_lock(:lock_id)"), {"lock_id": _ADVISORY_LOCK_ID}
        )
        if locked is not True:
            raise pytest.UsageError(
                "another AgentPost PostgreSQL acceptance suite holds the test database lock"
            )
        try:
            yield url
        finally:
            connection.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": _ADVISORY_LOCK_ID}
            )
    guard_engine.dispose()


@pytest.fixture
def migrated_database(postgres_url: str) -> Iterator[Database]:
    """Create a clean schema exclusively through the production Alembic chain."""

    config = _alembic_config(postgres_url)
    with _migration_environment(postgres_url):
        command.downgrade(config, "base")
        command.upgrade(config, "head")

    database = Database(postgres_url)
    try:
        yield database
    finally:
        database.dispose()
        with _migration_environment(postgres_url):
            command.downgrade(config, "base")
