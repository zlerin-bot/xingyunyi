from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from agentpost.config import Settings
from agentpost.db import Database
from agentpost.security.models import RateLimitBucket
from agentpost.security.rate_limit import RateLimitExceededError, enforce_rate_limit


def test_rate_limit_is_atomic_and_stores_only_subject_digest(database: Database) -> None:
    settings = Settings(rate_limit_secret="rate-limit-test-secret")
    now = datetime(2026, 8, 24, 2, 0, tzinfo=UTC)
    with database.session_factory() as session:
        enforce_rate_limit(
            session,
            settings,
            scope="human_login_account",
            subject="email:owner@example.com",
            limit=1,
            window_seconds=900,
            now=now,
        )
        with pytest.raises(RateLimitExceededError) as exc:
            enforce_rate_limit(
                session,
                settings,
                scope="human_login_account",
                subject="email:owner@example.com",
                limit=1,
                window_seconds=900,
                now=now + timedelta(seconds=10),
            )
        bucket = session.scalar(select(RateLimitBucket))

    assert exc.value.retry_after == 891
    assert bucket is not None and bucket.request_count == 2
    assert bucket.subject_digest != "email:owner@example.com"
    assert "owner@example.com" not in repr(bucket.__dict__)


def test_rate_limit_windows_and_subjects_are_isolated(database: Database) -> None:
    settings = Settings(rate_limit_secret="rate-limit-test-secret")
    first = datetime(2026, 8, 24, 2, 0, tzinfo=UTC)
    with database.session_factory() as session:
        for subject, now in [
            ("ip:192.0.2.1", first),
            ("ip:192.0.2.2", first),
            ("ip:192.0.2.1", first + timedelta(minutes=16)),
        ]:
            enforce_rate_limit(
                session,
                settings,
                scope="human_login_ip",
                subject=subject,
                limit=1,
                window_seconds=900,
                now=now,
            )
        buckets = session.scalars(select(RateLimitBucket)).all()

    assert len(buckets) == 3


def test_disabled_rate_limit_does_not_persist_bucket(database: Database) -> None:
    settings = Settings(rate_limit_enabled=False)
    with database.session_factory() as session:
        enforce_rate_limit(
            session,
            settings,
            scope="human_login_ip",
            subject="ip:192.0.2.1",
            limit=1,
            window_seconds=60,
        )
        assert session.scalar(select(RateLimitBucket)) is None
