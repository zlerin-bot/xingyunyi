from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from agentpost.config import Settings
from agentpost.control.auth import CurrentHumanDep
from agentpost.control.human_security import (
    HUMAN_CONFIRMATION_MARKER,
    HumanConfirmationInvalidError,
    HumanCsrfDep,
    consume_human_confirmation,
    create_human_confirmation,
)
from agentpost.control.models import (
    HumanActionAudit,
    HumanActionConfirmation,
    HumanSession,
    HumanUser,
)
from agentpost.db import Database
from agentpost.main import create_app

ADMIN_KEY = "admin-secret-admin-secret-admin-secret"


def _settings(settings: Settings) -> Settings:
    return Settings(
        environment="test",
        database_url=settings.database_url,
        storage_path=settings.storage_path,
        api_key_pepper="test-agent-pepper",
        human_api_key_pepper="test-human-pepper",
        cursor_secret="test-cursor-secret",
        registration_token="register-secret",
        admin_token=ADMIN_KEY,
        human_confirmation_ttl_seconds=300,
        log_level="WARNING",
    )


def _app(settings: Settings, database: Database) -> FastAPI:
    app = create_app(settings=_settings(settings), database=database)

    @app.post("/api/v1/orbit/test-human-write")
    def protected_human_write(
        current_human: CurrentHumanDep,
        csrf_guard: HumanCsrfDep,
    ) -> dict[str, str]:
        del csrf_guard
        return {"human_id": str(current_human.id)}

    return app


def _create_human(client: TestClient, *, email: str = "owner@example.com") -> dict[str, object]:
    response = client.post(
        "/api/v1/admin/humans",
        headers={"Authorization": f"Bearer {ADMIN_KEY}"},
        json={"email": email, "display_name": "北辰"},
    )
    assert response.status_code == 201
    return response.json()


def _login(client: TestClient, human: dict[str, object]) -> dict[str, object]:
    response = client.post(
        "/api/v1/orbit/session",
        headers={"Authorization": f"Bearer {human['access_key']}"},
    )
    assert response.status_code == 201
    return response.json()


def test_browser_csrf_is_hashed_rotated_and_required_for_writes(
    settings: Settings,
    database: Database,
) -> None:
    with TestClient(_app(settings, database)) as client:
        human = _create_human(client)
        login = _login(client, human)
        original = str(login["csrf_token"])
        assert original.startswith("csrf_")

        missing = client.post("/api/v1/orbit/test-human-write")
        wrong = client.post(
            "/api/v1/orbit/test-human-write",
            headers={"X-CSRF-Token": "csrf_wrong"},
        )
        accepted = client.post(
            "/api/v1/orbit/test-human-write",
            headers={"X-CSRF-Token": original},
        )
        refreshed = client.get("/api/v1/orbit/session")
        rotated = str(refreshed.json()["csrf_token"])
        stale = client.post(
            "/api/v1/orbit/test-human-write",
            headers={"X-CSRF-Token": original},
        )
        current = client.post(
            "/api/v1/orbit/test-human-write",
            headers={"X-CSRF-Token": rotated},
        )

    assert missing.status_code == wrong.status_code == stale.status_code == 403
    assert missing.json()["error"]["code"] == "INVALID_CSRF_TOKEN"
    assert accepted.status_code == current.status_code == 200
    assert refreshed.status_code == 200
    assert rotated.startswith("csrf_") and rotated != original
    assert refreshed.headers["Cache-Control"] == "no-store"

    with database.session_factory() as session:
        browser_session = session.scalar(select(HumanSession))
        audits = session.scalars(
            select(HumanActionAudit).where(HumanActionAudit.action == "control.csrf_validation")
        ).all()
        assert browser_session is not None
        assert browser_session.csrf_token_digest not in {original, rotated}
        assert original not in browser_session.csrf_token_digest
        assert rotated not in browser_session.csrf_token_digest
        assert len(audits) == 3
        assert {audit.reason_code for audit in audits} == {"invalid_csrf_token"}


def test_programmatic_human_bearer_does_not_require_browser_csrf(
    settings: Settings,
    database: Database,
) -> None:
    with TestClient(_app(settings, database)) as client:
        human = _create_human(client)
        response = client.post(
            "/api/v1/orbit/test-human-write",
            headers={"Authorization": f"Bearer {human['access_key']}"},
        )

    assert response.status_code == 200
    assert response.json()["human_id"] == human["user"]["id"]


def test_confirmation_is_single_use_short_lived_and_bound_to_action(
    settings: Settings,
    database: Database,
) -> None:
    protected = _settings(settings)
    with TestClient(_app(settings, database)) as client:
        human_payload = _create_human(client)
        _login(client, human_payload)

    human_id = UUID(str(human_payload["user"]["id"]))
    with database.session_factory() as session:
        human = session.get(HumanUser, human_id)
        browser_session = session.scalar(select(HumanSession))
        assert human is not None and browser_session is not None
        created = create_human_confirmation(
            session,
            protected,
            user=human,
            human_session_id=browser_session.id,
            intent="approve",
            target_type="approval_request",
            target_id="apr_example",
            request_id="request-confirmation",
        )
        assert created.raw_token.startswith(HUMAN_CONFIRMATION_MARKER)

    with database.session_factory() as session:
        human = session.get(HumanUser, human_id)
        browser_session = session.scalar(select(HumanSession))
        stored = session.scalar(select(HumanActionConfirmation))
        assert human is not None and browser_session is not None and stored is not None
        assert stored.token_digest != created.raw_token
        assert created.raw_token not in stored.token_digest

        with pytest.raises(HumanConfirmationInvalidError):
            consume_human_confirmation(
                session,
                protected,
                user=human,
                human_session_id=browser_session.id,
                intent="reject",
                target_type="approval_request",
                target_id="apr_example",
                raw_token=created.raw_token,
            )

        consumed = consume_human_confirmation(
            session,
            protected,
            user=human,
            human_session_id=browser_session.id,
            intent="approve",
            target_type="approval_request",
            target_id="apr_example",
            raw_token=created.raw_token,
        )
        session.commit()
        assert consumed.consumed_at is not None

        with pytest.raises(HumanConfirmationInvalidError):
            consume_human_confirmation(
                session,
                protected,
                user=human,
                human_session_id=browser_session.id,
                intent="approve",
                target_type="approval_request",
                target_id="apr_example",
                raw_token=created.raw_token,
            )


def test_expired_confirmation_is_rejected(
    settings: Settings,
    database: Database,
) -> None:
    protected = _settings(settings)
    with TestClient(_app(settings, database)) as client:
        human_payload = _create_human(client)
        _login(client, human_payload)

    human_id = UUID(str(human_payload["user"]["id"]))
    with database.session_factory() as session:
        human = session.get(HumanUser, human_id)
        browser_session = session.scalar(select(HumanSession))
        assert human is not None and browser_session is not None
        created = create_human_confirmation(
            session,
            protected,
            user=human,
            human_session_id=browser_session.id,
            intent="reject",
            target_type="approval_request",
            target_id="apr_expired",
            request_id="request-expired",
        )
        confirmation = session.scalar(select(HumanActionConfirmation))
        assert confirmation is not None
        confirmation.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()

    with database.session_factory() as session:
        human = session.get(HumanUser, human_id)
        browser_session = session.scalar(select(HumanSession))
        assert human is not None and browser_session is not None
        with pytest.raises(HumanConfirmationInvalidError):
            consume_human_confirmation(
                session,
                protected,
                user=human,
                human_session_id=browser_session.id,
                intent="reject",
                target_type="approval_request",
                target_id="apr_expired",
                raw_token=created.raw_token,
            )

        audit = session.scalar(
            select(HumanActionAudit).where(
                HumanActionAudit.action == "control.action_confirmation_created"
            )
        )
        assert audit is not None
        assert audit.human_user_id == human_id
        assert audit.target_id == "apr_expired"
        assert audit.outcome == "success"
