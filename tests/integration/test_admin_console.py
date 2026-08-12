from __future__ import annotations

from fastapi.testclient import TestClient

from agentpost.config import Settings
from agentpost.db import Database
from agentpost.main import create_app


def _protected_client(settings: Settings, database: Database) -> TestClient:
    protected = Settings(
        environment="test",
        database_url=settings.database_url,
        storage_path=settings.storage_path,
        api_key_pepper="test-pepper",
        cursor_secret="test-cursor-secret",
        registration_token="register-secret",
        admin_token="admin-secret-admin-secret-admin-secret",
        log_level="WARNING",
    )
    return TestClient(create_app(settings=protected, database=database))


def test_admin_surface_is_hidden_when_disabled(client: TestClient) -> None:
    for path in ("/admin", "/api/v1/admin/agents", "/api/v1/admin/audit-logs"):
        response = client.get(path, headers={"Authorization": "Bearer anything"})
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"


def test_admin_token_is_required_and_never_returned(
    settings: Settings,
    database: Database,
) -> None:
    with _protected_client(settings, database) as client:
        missing = client.get("/api/v1/admin/agents")
        wrong = client.get("/api/v1/admin/agents", headers={"Authorization": "Bearer wrong"})
        good = client.get(
            "/api/v1/admin/agents",
            headers={"Authorization": "Bearer admin-secret-admin-secret-admin-secret"},
        )

    assert missing.status_code == wrong.status_code == 404
    assert good.status_code == 200
    assert good.json() == {"items": []}
    assert "admin-secret" not in good.text


def test_admin_can_inspect_safe_operational_metadata_without_message_body(
    settings: Settings,
    database: Database,
) -> None:
    headers = {"Authorization": "Bearer admin-secret-admin-secret-admin-secret"}
    with _protected_client(settings, database) as client:
        alice = client.post(
            "/api/v1/agents",
            headers={"X-Registration-Token": "register-secret"},
            json={"address": "alice@agents.local", "display_name": "Alice"},
        ).json()
        bob = client.post(
            "/api/v1/agents",
            headers={"X-Registration-Token": "register-secret"},
            json={"address": "bob@agents.local", "display_name": "Bob"},
        ).json()
        sent = client.post(
            "/api/v1/messages",
            headers={
                "Authorization": f"Bearer {alice['api_key']}",
                "Idempotency-Key": "admin-inspection-message",
            },
            json={
                "to": [{"address": "bob@agents.local"}],
                "type": "message",
                "subject": "Safe subject",
                "content": {"format": "text", "body": "message-body-secret"},
            },
        )
        assert sent.status_code == 201

        agents = client.get("/api/v1/admin/agents", headers=headers)
        messages = client.get("/api/v1/admin/messages", headers=headers)
        threads = client.get("/api/v1/admin/threads", headers=headers)
        deliveries = client.get("/api/v1/admin/deliveries", headers=headers)
        audit = client.get("/api/v1/admin/audit-logs", headers=headers)

    assert {item["address"] for item in agents.json()["items"]} == {
        "alice@agents.local",
        "bob@agents.local",
    }
    assert messages.json()["items"][0]["message_id"] == sent.json()["message_id"]
    assert threads.json()["items"][0]["message_count"] == 1
    assert deliveries.json()["items"][0]["status"] == "delivered"
    assert audit.json()["items"][0]["action"] == "message.accepted"
    rendered = "".join(response.text for response in (agents, messages, threads, deliveries, audit))
    assert "message-body-secret" not in rendered
    assert alice["api_key"] not in rendered
    assert bob["api_key"] not in rendered
    assert "key_digest" not in rendered


def test_admin_console_has_security_headers_and_no_persistent_token_storage(
    settings: Settings,
    database: Database,
) -> None:
    with _protected_client(settings, database) as client:
        response = client.get("/admin")
        stylesheet = client.get("/admin/styles.css")
        script = client.get("/admin/app.js")

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert stylesheet.status_code == 200
    assert stylesheet.headers["content-type"].startswith("text/css")
    assert script.status_code == 200
    assert "javascript" in script.headers["content-type"]
    lowered = response.text.casefold()
    assert "localstorage" not in lowered
    assert "sessionstorage" not in lowered
    assert "innerhtml" not in lowered
