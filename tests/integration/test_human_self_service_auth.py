from __future__ import annotations

import time

from fastapi.testclient import TestClient
from sqlalchemy import select

from agentpost.accounts.crypto import totp_at_step
from agentpost.accounts.models import (
    HumanEmailChallenge,
    HumanPasswordCredential,
    HumanTotpCredential,
)
from agentpost.config import Settings
from agentpost.control.models import HumanAccessKey, HumanSession, HumanUser
from agentpost.db import Database
from agentpost.main import create_app
from agentpost.security.models import RateLimitBucket


def _settings(settings: Settings, *, enabled: bool = True) -> Settings:
    return Settings(
        environment="test",
        database_url=settings.database_url,
        storage_path=settings.storage_path,
        api_key_pepper="test-agent-pepper",
        human_api_key_pepper="test-human-key-pepper",
        human_auth_secret="test-human-auth-secret",
        human_mfa_encryption_key="test-human-mfa-encryption-key",
        cursor_secret="test-cursor-secret",
        pairing_secret="test-pairing-secret",
        human_self_service_enabled=True,
        open_registration_enabled=enabled,
        email_delivery_mode="test",
        email_challenge_cooldown_seconds=10,
        log_level="WARNING",
    )


def _start(client: TestClient, email: str, purpose: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/auth/email/challenges",
        json={"email": email, "purpose": purpose},
    )
    assert response.status_code == 202, response.text
    payload = response.json()
    assert payload["delivery"] == "email"
    assert len(payload["test_verification_code"]) == 8
    return payload


def _register(client: TestClient, email: str = "owner@example.com") -> dict[str, object]:
    challenge = _start(client, email, "register")
    response = client.post(
        "/api/v1/auth/register",
        json={
            "challenge_id": challenge["challenge_id"],
            "code": challenge["test_verification_code"],
            "display_name": "Self Service Owner",
            "password": "correct horse battery staple",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["auth_method"] == "email_password"
    assert response.json()["mfa_authenticated"] is False
    assert client.cookies.get("xinggui_session", "").startswith("hss_")
    return response.json()


def _logout(client: TestClient, csrf: str) -> None:
    response = client.delete(
        "/api/v1/orbit/session",
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 204, response.text


def test_open_registration_is_closed_by_default(
    settings: Settings,
    database: Database,
) -> None:
    with TestClient(
        create_app(settings=_settings(settings, enabled=False), database=database)
    ) as client:
        response = client.post(
            "/api/v1/auth/email/challenges",
            json={"email": "closed@example.com", "purpose": "register"},
        )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "OPEN_REGISTRATION_DISABLED"


def test_email_registration_login_and_secret_storage(
    settings: Settings,
    database: Database,
) -> None:
    runtime = _settings(settings)
    with TestClient(create_app(settings=runtime, database=database)) as client:
        registered = _register(client)
        csrf = registered["csrf_token"]
        dashboard = client.get("/api/v1/orbit/dashboard")
        assert dashboard.status_code == 200
        _logout(client, csrf)

        login = client.post(
            "/api/v1/auth/login",
            json={
                "email": "OWNER@EXAMPLE.COM",
                "password": "correct horse battery staple",
            },
        )
        assert login.status_code == 200, login.text
        assert login.json()["user"]["email"] == "owner@example.com"

    with database.session_factory() as session:
        user = session.scalar(select(HumanUser).where(HumanUser.email == "owner@example.com"))
        assert user is not None and user.email_verified_at is not None
        password = session.get(HumanPasswordCredential, user.id)
        assert password is not None
        assert "correct horse" not in password.password_hash
        assert (
            session.scalar(select(HumanAccessKey).where(HumanAccessKey.human_user_id == user.id))
            is None
        )
        challenge = session.scalar(select(HumanEmailChallenge))
        assert challenge is not None
        assert challenge.code_digest != ""
        assert challenge.consumed_at is not None


def test_email_challenge_rate_limit_and_attempt_budget(
    settings: Settings,
    database: Database,
) -> None:
    with TestClient(create_app(settings=_settings(settings), database=database)) as client:
        challenge = _start(client, "rate@example.com", "register")
        limited = client.post(
            "/api/v1/auth/email/challenges",
            json={"email": "rate@example.com", "purpose": "register"},
        )
        assert limited.status_code == 429
        assert int(limited.headers["Retry-After"]) >= 1
        for _ in range(5):
            invalid = client.post(
                "/api/v1/auth/register",
                json={
                    "challenge_id": challenge["challenge_id"],
                    "code": "00000000",
                    "display_name": "Rate",
                    "password": "correct horse battery staple",
                },
            )
            assert invalid.status_code == 400
        exhausted = client.post(
            "/api/v1/auth/register",
            json={
                "challenge_id": challenge["challenge_id"],
                "code": challenge["test_verification_code"],
                "display_name": "Rate",
                "password": "correct horse battery staple",
            },
        )
        assert exhausted.status_code == 400


def test_login_has_durable_account_rate_limit_without_storing_email(
    settings: Settings,
    database: Database,
) -> None:
    runtime = _settings(settings).model_copy(
        update={
            "human_login_account_limit": 2,
            "human_login_ip_limit": 20,
            "human_login_rate_window_seconds": 900,
        }
    )
    with TestClient(create_app(settings=runtime, database=database)) as client:
        registered = _register(client, "limited-login@example.com")
        _logout(client, str(registered["csrf_token"]))
        for _ in range(2):
            rejected = client.post(
                "/api/v1/auth/login",
                json={
                    "email": "limited-login@example.com",
                    "password": "wrong password that is long enough",
                },
            )
            assert rejected.status_code == 401
        limited = client.post(
            "/api/v1/auth/login",
            json={
                "email": "limited-login@example.com",
                "password": "correct horse battery staple",
            },
        )
        assert limited.status_code == 429
        assert limited.json()["error"]["code"] == "RATE_LIMITED"
        assert int(limited.headers["Retry-After"]) >= 1

    with database.session_factory() as session:
        buckets = session.scalars(
            select(RateLimitBucket).where(RateLimitBucket.scope == "human_login_account")
        ).all()
    assert len(buckets) == 1 and buckets[0].request_count == 3
    assert "limited-login@example.com" not in repr(buckets[0].__dict__)


def test_totp_recovery_codes_and_human_key_rotation(
    settings: Settings,
    database: Database,
) -> None:
    runtime = _settings(settings)
    with TestClient(create_app(settings=runtime, database=database)) as client:
        registered = _register(client, "mfa@example.com")
        csrf = registered["csrf_token"]
        setup = client.post(
            "/api/v1/orbit/security/totp/setup",
            headers={"X-CSRF-Token": csrf},
            json={"password": "correct horse battery staple"},
        )
        assert setup.status_code == 200, setup.text
        secret = setup.json()["secret"]
        assert setup.json()["provisioning_uri"].startswith("otpauth://totp/")
        current_code = totp_at_step(secret, int(time.time() // 30))
        confirm = client.post(
            "/api/v1/orbit/security/totp/confirm",
            headers={"X-CSRF-Token": csrf},
            json={"code": current_code},
        )
        assert confirm.status_code == 200, confirm.text
        recovery_codes = confirm.json()["recovery_codes"]
        assert len(recovery_codes) == 10
        _logout(client, csrf)

        missing = client.post(
            "/api/v1/auth/login",
            json={"email": "mfa@example.com", "password": "correct horse battery staple"},
        )
        assert missing.status_code == 409
        replayed_totp = client.post(
            "/api/v1/auth/login",
            json={
                "email": "mfa@example.com",
                "password": "correct horse battery staple",
                "totp_code": current_code,
            },
        )
        assert replayed_totp.status_code == 401
        login = client.post(
            "/api/v1/auth/login",
            json={
                "email": "mfa@example.com",
                "password": "correct horse battery staple",
                "recovery_code": recovery_codes[0],
            },
        )
        assert login.status_code == 200, login.text
        assert login.json()["mfa_authenticated"] is True
        csrf = login.json()["csrf_token"]

        rotated = client.post(
            "/api/v1/orbit/security/human-keys/rotate",
            headers={"X-CSRF-Token": csrf},
            json={
                "password": "correct horse battery staple",
                "recovery_code": recovery_codes[1],
                "label": "CLI compatibility",
            },
        )
        assert rotated.status_code == 200, rotated.text
        raw_human_key = rotated.json()["access_key"]
        assert raw_human_key.startswith("hum_")
        assert raw_human_key not in repr(rotated.json()["key_prefix"])

        legacy_login = client.post(
            "/api/v1/orbit/session",
            headers={"Authorization": f"Bearer {raw_human_key}"},
        )
        assert legacy_login.status_code == 201, legacy_login.text

    with database.session_factory() as session:
        user = session.scalar(select(HumanUser).where(HumanUser.email == "mfa@example.com"))
        assert user is not None
        totp = session.get(HumanTotpCredential, user.id)
        assert totp is not None and totp.enabled_at is not None
        assert secret not in totp.encrypted_secret
        assert all(item not in totp.recovery_code_digests for item in recovery_codes)


def test_account_recovery_revokes_sessions_and_human_keys(
    settings: Settings,
    database: Database,
) -> None:
    runtime = _settings(settings)
    with TestClient(create_app(settings=runtime, database=database)) as client:
        registered = _register(client, "recover@example.com")
        csrf = registered["csrf_token"]
        first_key = client.post(
            "/api/v1/orbit/security/human-keys/rotate",
            headers={"X-CSRF-Token": csrf},
            json={"password": "correct horse battery staple", "label": "before recovery"},
        )
        assert first_key.status_code == 200
        raw_key = first_key.json()["access_key"]
        recovery = _start(client, "recover@example.com", "recover")
        completed = client.post(
            "/api/v1/auth/recover",
            json={
                "challenge_id": recovery["challenge_id"],
                "code": recovery["test_verification_code"],
                "new_password": "new correct horse battery staple",
            },
        )
        assert completed.status_code == 200, completed.text
        old_key = client.post(
            "/api/v1/orbit/session",
            headers={"Authorization": f"Bearer {raw_key}"},
        )
        assert old_key.status_code == 401
        old_password = client.post(
            "/api/v1/auth/login",
            json={"email": "recover@example.com", "password": "correct horse battery staple"},
        )
        assert old_password.status_code == 401
        new_password = client.post(
            "/api/v1/auth/login",
            json={
                "email": "recover@example.com",
                "password": "new correct horse battery staple",
            },
        )
        assert new_password.status_code == 200

    with database.session_factory() as session:
        assert (
            session.scalar(select(HumanSession).where(HumanSession.revoked_at.is_(None)))
            is not None
        )
        assert (
            session.scalar(select(HumanAccessKey).where(HumanAccessKey.revoked_at.is_(None)))
            is None
        )


def test_self_service_human_can_pair_without_a_human_key(
    settings: Settings,
    database: Database,
) -> None:
    runtime = _settings(settings)
    with TestClient(create_app(settings=runtime, database=database)) as client:
        registered = _register(client, "pair@example.com")
        pairing = client.post(
            "/api/v1/connect/pairings",
            json={
                "connector_type": "codex",
                "display_name": "Codex on local Mac",
                "capabilities": ["document-analysis"],
            },
        )
        assert pairing.status_code == 201, pairing.text
        pairing_payload = pairing.json()
        confirmation = client.post(
            f"/api/v1/orbit/pairings/{pairing_payload['pairing_id']}/confirmation",
            headers={"X-CSRF-Token": registered["csrf_token"]},
            json={
                "intent": "approve",
                "user_code": pairing_payload["user_code"],
                "password": "correct horse battery staple",
            },
        )
        assert confirmation.status_code == 200, confirmation.text
        decision = client.post(
            f"/api/v1/orbit/pairings/{pairing_payload['pairing_id']}/decision",
            headers={
                "X-CSRF-Token": registered["csrf_token"],
                "X-Human-Confirmation": confirmation.json()["confirmation_token"],
                "Idempotency-Key": "self-service-pairing",
            },
            json={"decision": "approved", "local_agent_id": "self-service-agent"},
        )
        assert decision.status_code == 200, decision.text
        claimed = client.post(
            "/api/v1/connect/pairings/token",
            json={"device_code": pairing_payload["device_code"]},
        )
        assert claimed.status_code == 200, claimed.text
        assert claimed.json()["agent"]["address"] == "self-service-agent@agents.local"

    with database.session_factory() as session:
        user = session.scalar(select(HumanUser).where(HumanUser.email == "pair@example.com"))
        assert user is not None
        assert (
            session.scalar(select(HumanAccessKey).where(HumanAccessKey.human_user_id == user.id))
            is None
        )
