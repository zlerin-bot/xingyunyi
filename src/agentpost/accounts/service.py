from __future__ import annotations

import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agentpost.accounts.crypto import (
    decrypt_totp_secret,
    digest_email_code,
    digest_recovery_code,
    encrypt_totp_secret,
    generate_email_code,
    generate_recovery_codes,
    generate_totp_secret,
    hash_password,
    totp_uri,
    validate_password,
    verify_password,
    verify_totp,
)
from agentpost.accounts.mailer import deliver_verification_code
from agentpost.accounts.models import (
    HumanEmailChallenge,
    HumanPasswordCredential,
    HumanTotpCredential,
)
from agentpost.accounts.schemas import (
    EmailChallengeStart,
    HumanKeyRotate,
    HumanLogin,
    RecoveryComplete,
    RegistrationComplete,
    SecurityOverview,
    TotpSetupStart,
)
from agentpost.config import Settings
from agentpost.control.api_keys import digest_human_key, generate_human_key, human_key_prefix
from agentpost.control.models import HumanAccessKey, HumanSession, HumanUser
from agentpost.identity.models import utc_now
from agentpost.messaging.models import AuditLog


class OpenRegistrationDisabledError(Exception):
    pass


class HumanSelfServiceDisabledError(Exception):
    pass


class EmailChallengeRateLimitedError(Exception):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after


class EmailChallengeInvalidError(Exception):
    pass


class EmailAlreadyRegisteredError(Exception):
    pass


class AuthenticationFailedError(Exception):
    pass


class MfaRequiredError(Exception):
    pass


class MfaInvalidError(Exception):
    pass


class PasswordNotConfiguredError(Exception):
    pass


class TotpInvalidStateError(Exception):
    pass


@dataclass(frozen=True)
class CreatedEmailChallenge:
    challenge: HumanEmailChallenge
    raw_code: str


@dataclass(frozen=True)
class RotatedHumanKey:
    raw_key: str
    credential: HumanAccessKey


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _challenge_id() -> str:
    return f"emc_{secrets.token_urlsafe(24)}"


def _audit(
    session: Session,
    *,
    action: str,
    target_type: str,
    target_id: str,
    request_id: str,
    outcome: str = "success",
    metadata: dict[str, object] | None = None,
) -> None:
    session.add(
        AuditLog(
            actor_agent_id=None,
            action=action,
            target_type=target_type,
            target_id=target_id,
            outcome=outcome,
            request_id=request_id,
            audit_metadata=metadata or {},
            created_at=utc_now(),
        )
    )


def create_email_challenge(
    session: Session,
    settings: Settings,
    *,
    payload: EmailChallengeStart,
    request_id: str,
) -> CreatedEmailChallenge:
    if not settings.human_self_service_enabled:
        raise HumanSelfServiceDisabledError
    if payload.purpose == "register" and not settings.open_registration_enabled:
        raise OpenRegistrationDisabledError
    now = utc_now()
    latest = session.scalar(
        select(HumanEmailChallenge)
        .where(
            HumanEmailChallenge.email == payload.email,
            HumanEmailChallenge.purpose == payload.purpose,
        )
        .order_by(HumanEmailChallenge.created_at.desc())
        .limit(1)
    )
    if latest is not None:
        elapsed = (now - _as_utc(latest.created_at)).total_seconds()
        if elapsed < settings.email_challenge_cooldown_seconds:
            raise EmailChallengeRateLimitedError(
                max(1, int(settings.email_challenge_cooldown_seconds - elapsed) + 1)
            )
    raw_code = generate_email_code()
    challenge = HumanEmailChallenge(
        challenge_id=_challenge_id(),
        email=payload.email,
        purpose=payload.purpose,
        code_digest="",
        expires_at=now + timedelta(seconds=settings.email_challenge_ttl_seconds),
        created_at=now,
    )
    challenge.code_digest = digest_email_code(
        challenge.challenge_id,
        raw_code,
        settings.human_auth_secret,
    )
    session.add(challenge)
    session.flush()
    deliver_verification_code(
        settings,
        email=payload.email,
        code=raw_code,
        purpose=payload.purpose,
    )
    _audit(
        session,
        action="account.email_challenge_created",
        target_type="human_email_challenge",
        target_id=challenge.challenge_id,
        request_id=request_id,
        metadata={"purpose": payload.purpose},
    )
    session.commit()
    return CreatedEmailChallenge(challenge=challenge, raw_code=raw_code)


def _verify_challenge(
    session: Session,
    settings: Settings,
    *,
    challenge_id: str,
    code: str,
    purpose: str,
) -> HumanEmailChallenge:
    challenge = session.scalar(
        select(HumanEmailChallenge)
        .where(HumanEmailChallenge.challenge_id == challenge_id)
        .with_for_update()
    )
    now = utc_now()
    if (
        challenge is None
        or challenge.purpose != purpose
        or challenge.consumed_at is not None
        or _as_utc(challenge.expires_at) <= now
        or challenge.attempts >= settings.email_challenge_max_attempts
    ):
        raise EmailChallengeInvalidError
    candidate = digest_email_code(challenge.challenge_id, code, settings.human_auth_secret)
    if not hmac.compare_digest(candidate, challenge.code_digest):
        challenge.attempts += 1
        session.commit()
        raise EmailChallengeInvalidError
    challenge.verified_at = challenge.verified_at or now
    return challenge


def complete_registration(
    session: Session,
    settings: Settings,
    *,
    payload: RegistrationComplete,
    request_id: str,
) -> HumanUser:
    if not settings.human_self_service_enabled:
        raise HumanSelfServiceDisabledError
    if not settings.open_registration_enabled:
        raise OpenRegistrationDisabledError
    password = validate_password(payload.password.get_secret_value())
    challenge = _verify_challenge(
        session,
        settings,
        challenge_id=payload.challenge_id,
        code=payload.code,
        purpose="register",
    )
    if session.scalar(select(HumanUser.id).where(HumanUser.email == challenge.email)) is not None:
        session.rollback()
        raise EmailAlreadyRegisteredError
    now = utc_now()
    salt, password_hash = hash_password(password)
    user = HumanUser(
        email=challenge.email,
        display_name=payload.display_name,
        status="active",
        email_verified_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(user)
    try:
        session.flush()
        session.add(
            HumanPasswordCredential(
                human_user_id=user.id,
                salt=salt,
                password_hash=password_hash,
                created_at=now,
                updated_at=now,
            )
        )
        challenge.consumed_at = now
        _audit(
            session,
            action="account.human_registered",
            target_type="human_user",
            target_id=str(user.id),
            request_id=request_id,
            metadata={"auth_method": "email_password"},
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise EmailAlreadyRegisteredError from exc
    return user


def _password_credential(session: Session, user: HumanUser) -> HumanPasswordCredential:
    credential = session.get(HumanPasswordCredential, user.id)
    if credential is None:
        raise PasswordNotConfiguredError
    return credential


def _consume_recovery_code(
    credential: HumanTotpCredential,
    code: str,
    settings: Settings,
) -> bool:
    candidate = digest_recovery_code(code, settings.human_auth_secret)
    digests = [item for item in credential.recovery_code_digests.split(",") if item]
    for index, digest in enumerate(digests):
        if hmac.compare_digest(candidate, digest):
            del digests[index]
            credential.recovery_code_digests = ",".join(digests)
            return True
    return False


def verify_mfa_proof(
    session: Session,
    settings: Settings,
    *,
    user: HumanUser,
    totp_code: str | None,
    recovery_code: str | None,
) -> bool:
    credential = session.get(HumanTotpCredential, user.id)
    if credential is None or credential.pending or credential.enabled_at is None:
        return False
    if recovery_code and _consume_recovery_code(credential, recovery_code, settings):
        return True
    if not totp_code:
        raise MfaRequiredError
    secret = decrypt_totp_secret(
        credential.encrypted_secret,
        settings.human_mfa_encryption_key,
    )
    accepted_step = verify_totp(
        secret,
        totp_code,
        last_used_step=credential.last_used_step,
    )
    if accepted_step is None:
        raise MfaInvalidError
    credential.last_used_step = accepted_step
    return True


def authenticate_human(
    session: Session,
    settings: Settings,
    *,
    payload: HumanLogin,
    request_id: str,
) -> tuple[HumanUser, bool]:
    if not settings.human_self_service_enabled:
        raise HumanSelfServiceDisabledError
    user = session.scalar(select(HumanUser).where(HumanUser.email == payload.email))
    if user is None or user.status != "active":
        supplied = payload.password.get_secret_value()[:220]
        hash_password(f"{supplied}invalid-password-padding")
        raise AuthenticationFailedError
    credential = _password_credential(session, user)
    if not verify_password(
        payload.password.get_secret_value(),
        credential.salt,
        credential.password_hash,
    ):
        raise AuthenticationFailedError
    totp = session.get(HumanTotpCredential, user.id)
    mfa_enabled = bool(totp and not totp.pending and totp.enabled_at)
    if mfa_enabled:
        verify_mfa_proof(
            session,
            settings,
            user=user,
            totp_code=payload.totp_code,
            recovery_code=payload.recovery_code,
        )
    _audit(
        session,
        action="account.login_succeeded",
        target_type="human_user",
        target_id=str(user.id),
        request_id=request_id,
        metadata={"mfa": mfa_enabled},
    )
    session.commit()
    return user, mfa_enabled


def recover_account(
    session: Session,
    settings: Settings,
    *,
    payload: RecoveryComplete,
    request_id: str,
) -> tuple[HumanUser, bool]:
    if not settings.human_self_service_enabled:
        raise HumanSelfServiceDisabledError
    password = validate_password(payload.new_password.get_secret_value())
    challenge = _verify_challenge(
        session,
        settings,
        challenge_id=payload.challenge_id,
        code=payload.code,
        purpose="recover",
    )
    user = session.scalar(select(HumanUser).where(HumanUser.email == challenge.email))
    if user is None or user.status != "active":
        session.rollback()
        raise EmailChallengeInvalidError
    totp = session.get(HumanTotpCredential, user.id)
    mfa_enabled = bool(totp and not totp.pending and totp.enabled_at)
    if mfa_enabled:
        verify_mfa_proof(
            session,
            settings,
            user=user,
            totp_code=payload.totp_code,
            recovery_code=payload.recovery_code,
        )
    salt, password_hash = hash_password(password)
    credential = session.get(HumanPasswordCredential, user.id)
    now = utc_now()
    if credential is None:
        credential = HumanPasswordCredential(
            human_user_id=user.id,
            salt=salt,
            password_hash=password_hash,
            created_at=now,
            updated_at=now,
        )
        session.add(credential)
    else:
        credential.salt = salt
        credential.password_hash = password_hash
        credential.updated_at = now
    for browser_session in session.scalars(
        select(HumanSession).where(
            HumanSession.human_user_id == user.id,
            HumanSession.revoked_at.is_(None),
        )
    ):
        browser_session.revoked_at = now
    for key in session.scalars(
        select(HumanAccessKey).where(
            HumanAccessKey.human_user_id == user.id,
            HumanAccessKey.revoked_at.is_(None),
        )
    ):
        key.revoked_at = now
    challenge.consumed_at = now
    _audit(
        session,
        action="account.recovered",
        target_type="human_user",
        target_id=str(user.id),
        request_id=request_id,
        metadata={"sessions_revoked": True, "human_keys_revoked": True},
    )
    session.commit()
    return user, mfa_enabled


def verify_password_and_mfa(
    session: Session,
    settings: Settings,
    *,
    user: HumanUser,
    password: str,
    totp_code: str | None,
    recovery_code: str | None,
) -> bool:
    credential = _password_credential(session, user)
    if not verify_password(password, credential.salt, credential.password_hash):
        raise AuthenticationFailedError
    totp = session.get(HumanTotpCredential, user.id)
    if totp is None or totp.pending or totp.enabled_at is None:
        return False
    verify_mfa_proof(
        session,
        settings,
        user=user,
        totp_code=totp_code,
        recovery_code=recovery_code,
    )
    return True


def verify_human_reauthentication(
    session: Session,
    settings: Settings,
    *,
    user: HumanUser,
    access_key_user: HumanUser | None,
    password: str | None,
    totp_code: str | None,
    recovery_code: str | None,
) -> str:
    if access_key_user is not None:
        if access_key_user.id != user.id:
            raise AuthenticationFailedError
        return "access_key"
    if password is None:
        raise AuthenticationFailedError
    mfa_authenticated = verify_password_and_mfa(
        session,
        settings,
        user=user,
        password=password,
        totp_code=totp_code,
        recovery_code=recovery_code,
    )
    session.commit()
    return "password_mfa" if mfa_authenticated else "password"


def begin_totp_setup(
    session: Session,
    settings: Settings,
    *,
    user: HumanUser,
    payload: TotpSetupStart,
) -> tuple[str, str]:
    verify_password_and_mfa(
        session,
        settings,
        user=user,
        password=payload.password.get_secret_value(),
        totp_code=payload.totp_code,
        recovery_code=payload.recovery_code,
    )
    secret = generate_totp_secret()
    credential = session.get(HumanTotpCredential, user.id)
    if credential is None:
        credential = HumanTotpCredential(human_user_id=user.id, encrypted_secret="")
        session.add(credential)
    credential.encrypted_secret = encrypt_totp_secret(
        secret,
        settings.human_mfa_encryption_key,
    )
    credential.pending = True
    credential.recovery_code_digests = ""
    credential.last_used_step = None
    credential.enabled_at = None
    session.commit()
    return secret, totp_uri(secret, email=user.email)


def confirm_totp_setup(
    session: Session,
    settings: Settings,
    *,
    user: HumanUser,
    code: str,
    request_id: str,
) -> list[str]:
    credential = session.get(HumanTotpCredential, user.id)
    if credential is None or not credential.pending:
        raise TotpInvalidStateError
    secret = decrypt_totp_secret(
        credential.encrypted_secret,
        settings.human_mfa_encryption_key,
    )
    accepted_step = verify_totp(secret, code)
    if accepted_step is None:
        raise MfaInvalidError
    recovery_codes = generate_recovery_codes()
    credential.pending = False
    credential.enabled_at = utc_now()
    credential.last_used_step = accepted_step
    credential.recovery_code_digests = ",".join(
        digest_recovery_code(item, settings.human_auth_secret) for item in recovery_codes
    )
    _audit(
        session,
        action="account.mfa_enabled",
        target_type="human_user",
        target_id=str(user.id),
        request_id=request_id,
    )
    session.commit()
    return recovery_codes


def disable_totp(
    session: Session,
    settings: Settings,
    *,
    user: HumanUser,
    password: str,
    totp_code: str | None,
    recovery_code: str | None,
    request_id: str,
) -> None:
    verify_password_and_mfa(
        session,
        settings,
        user=user,
        password=password,
        totp_code=totp_code,
        recovery_code=recovery_code,
    )
    credential = session.get(HumanTotpCredential, user.id)
    if credential is None or credential.pending:
        raise TotpInvalidStateError
    session.delete(credential)
    _audit(
        session,
        action="account.mfa_disabled",
        target_type="human_user",
        target_id=str(user.id),
        request_id=request_id,
    )
    session.commit()


def rotate_human_key(
    session: Session,
    settings: Settings,
    *,
    user: HumanUser,
    payload: HumanKeyRotate,
    request_id: str,
) -> RotatedHumanKey:
    verify_password_and_mfa(
        session,
        settings,
        user=user,
        password=payload.password.get_secret_value(),
        totp_code=payload.totp_code,
        recovery_code=payload.recovery_code,
    )
    now = utc_now()
    for existing in session.scalars(
        select(HumanAccessKey).where(
            HumanAccessKey.human_user_id == user.id,
            HumanAccessKey.revoked_at.is_(None),
        )
    ):
        existing.revoked_at = now
    raw_key = generate_human_key()
    credential = HumanAccessKey(
        human_user_id=user.id,
        key_digest=digest_human_key(raw_key, settings.human_api_key_pepper),
        key_prefix=human_key_prefix(raw_key),
        label=payload.label,
        created_at=now,
    )
    session.add(credential)
    _audit(
        session,
        action="account.human_key_rotated",
        target_type="human_user",
        target_id=str(user.id),
        request_id=request_id,
        metadata={"key_prefix": credential.key_prefix},
    )
    session.commit()
    return RotatedHumanKey(raw_key=raw_key, credential=credential)


def security_overview(session: Session, *, user: HumanUser) -> SecurityOverview:
    totp = session.get(HumanTotpCredential, user.id)
    return SecurityOverview(
        email_verified=user.email_verified_at is not None,
        password_configured=session.get(HumanPasswordCredential, user.id) is not None,
        mfa_enabled=bool(totp and not totp.pending and totp.enabled_at),
        active_human_keys=int(
            session.scalar(
                select(func.count())
                .select_from(HumanAccessKey)
                .where(
                    HumanAccessKey.human_user_id == user.id,
                    HumanAccessKey.revoked_at.is_(None),
                )
            )
            or 0
        ),
    )
