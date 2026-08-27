from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from agentpost.onboarding.connectivity import (
    connector_connection_state,
    heartbeat_timeout_seconds,
)


def connector(**overrides: object) -> SimpleNamespace:
    values = {
        "status": "active",
        "health_status": "healthy",
        "last_error_code": None,
        "last_heartbeat_at": datetime(2026, 8, 27, 0, 0, tzinfo=UTC),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_online_requires_a_current_healthy_heartbeat_within_three_intervals() -> None:
    now = datetime(2026, 8, 27, 0, 1, 30, tzinfo=UTC)

    assert heartbeat_timeout_seconds(30) == 90
    assert (
        connector_connection_state(connector(), now=now, heartbeat_interval_seconds=30)
        == "connected"
    )
    assert (
        connector_connection_state(
            connector(last_heartbeat_at=now - timedelta(seconds=91)),
            now=now,
            heartbeat_interval_seconds=30,
        )
        == "offline"
    )


def test_connection_states_do_not_treat_authorization_as_online() -> None:
    now = datetime(2026, 8, 27, 0, 1, 30, tzinfo=UTC)

    assert (
        connector_connection_state(None, now=now, heartbeat_interval_seconds=30) == "disconnected"
    )
    assert (
        connector_connection_state(
            connector(last_heartbeat_at=None), now=now, heartbeat_interval_seconds=30
        )
        == "awaiting_agent"
    )
    assert (
        connector_connection_state(
            connector(health_status="error", last_error_code="BROKEN"),
            now=now,
            heartbeat_interval_seconds=30,
        )
        == "connection_error"
    )
