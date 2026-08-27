from __future__ import annotations

from datetime import UTC, datetime, timedelta


def heartbeat_timeout_seconds(interval_seconds: int) -> int:
    """Allow three missed heartbeats, with a one-minute minimum grace period."""

    return max(60, interval_seconds * 3)


def connector_connection_state(
    connector: object | None,
    *,
    now: datetime,
    heartbeat_interval_seconds: int,
) -> str:
    if connector is None:
        return "disconnected"
    if getattr(connector, "status", None) != "active":
        return "connection_error"
    if getattr(connector, "health_status", None) == "error" or getattr(
        connector,
        "last_error_code",
        None,
    ):
        return "connection_error"
    heartbeat = getattr(connector, "last_heartbeat_at", None)
    if heartbeat is None:
        return "awaiting_agent"
    if heartbeat.tzinfo is None:
        heartbeat = heartbeat.replace(tzinfo=UTC)
    else:
        heartbeat = heartbeat.astimezone(UTC)
    timeout = timedelta(seconds=heartbeat_timeout_seconds(heartbeat_interval_seconds))
    if now.astimezone(UTC) - heartbeat > timeout:
        return "offline"
    return "connected"
