from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status

from agentpost.accounts.mailer import EmailDeliveryError
from agentpost.accounts.schemas import (
    BrowserAuthenticationResponse,
    EmailChallengeResponse,
    EmailChallengeStart,
    HumanAuthConfig,
    HumanKeyRotate,
    HumanKeyRotationResponse,
    HumanLogin,
    PasswordMfaProof,
    RecoveryComplete,
    RegistrationComplete,
    SecurityOverview,
    TotpEnabledResponse,
    TotpSetupConfirm,
    TotpSetupResponse,
    TotpSetupStart,
)
from agentpost.accounts.service import (
    AuthenticationFailedError,
    EmailAlreadyRegisteredError,
    EmailChallengeInvalidError,
    EmailChallengeRateLimitedError,
    HumanSelfServiceDisabledError,
    MfaInvalidError,
    MfaRequiredError,
    OpenRegistrationDisabledError,
    PasswordNotConfiguredError,
    TotpInvalidStateError,
    authenticate_human,
    begin_totp_setup,
    complete_registration,
    confirm_totp_setup,
    create_email_challenge,
    disable_totp,
    recover_account,
    rotate_human_key,
    security_overview,
)
from agentpost.api.dependencies import SessionDep, SettingsDep
from agentpost.control.auth import CurrentHumanDep
from agentpost.control.human_security import HumanCsrfDep
from agentpost.control.schemas import HumanProfile
from agentpost.control.service import human_profile
from agentpost.control.sessions import HUMAN_SESSION_COOKIE, create_human_session
from agentpost.security.rate_limit import (
    client_rate_limit_subject,
    enforce_http_rate_limit,
)

router = APIRouter(tags=["human-authentication"])


@router.get("/api/v1/auth/config", response_model=HumanAuthConfig)
def human_auth_config(settings: SettingsDep) -> HumanAuthConfig:
    return HumanAuthConfig(
        self_service_enabled=settings.human_self_service_enabled,
        open_registration_enabled=settings.open_registration_enabled,
        enterprise_oidc_enabled=settings.enterprise_oidc_enabled,
        managed_agent_domain=settings.managed_agent_domain,
    )


def _set_session_cookie(response: Response, settings: SettingsDep, raw_token: str) -> None:
    response.set_cookie(
        key=HUMAN_SESSION_COOKIE,
        value=raw_token,
        max_age=settings.human_session_ttl_seconds,
        path="/api/v1/orbit",
        secure=settings.is_production,
        httponly=True,
        samesite="strict",
    )
    response.headers["Cache-Control"] = "no-store"


def _authentication_response(
    response: Response,
    settings: SettingsDep,
    *,
    user: HumanProfile,
    raw_token: str,
    raw_csrf_token: str,
    expires_at,
    auth_method: str,
    mfa_authenticated: bool,
) -> BrowserAuthenticationResponse:
    _set_session_cookie(response, settings, raw_token)
    return BrowserAuthenticationResponse(
        user=user,
        csrf_token=raw_csrf_token,
        expires_at=expires_at,
        auth_method=auth_method,
        mfa_authenticated=mfa_authenticated,
    )


def _raise_auth_error(exc: Exception) -> None:
    if isinstance(exc, MfaRequiredError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "mfa_required", "message": "A current MFA proof is required"},
        ) from exc
    if isinstance(exc, MfaInvalidError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "mfa_invalid", "message": "The MFA proof is invalid or replayed"},
        ) from exc
    if isinstance(exc, PasswordNotConfiguredError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "password_not_configured",
                "message": "This legacy account must complete account recovery first",
            },
        ) from exc
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "authentication_failed", "message": "Email or password is invalid"},
    ) from exc


def _self_service_disabled() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "human_self_service_disabled", "message": "Human login is unavailable"},
    )


@router.post(
    "/api/v1/auth/email/challenges",
    response_model=EmailChallengeResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_email_challenge(
    payload: EmailChallengeStart,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
) -> EmailChallengeResponse:
    if not settings.human_self_service_enabled:
        raise _self_service_disabled()
    if payload.purpose == "register" and not settings.open_registration_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "open_registration_disabled", "message": "Registration is closed"},
        )
    enforce_http_rate_limit(
        request,
        session,
        settings,
        scope="human_email_challenge_ip",
        subject=client_rate_limit_subject(request),
        limit=settings.email_challenge_ip_limit,
        window_seconds=settings.email_challenge_rate_window_seconds,
    )
    enforce_http_rate_limit(
        request,
        session,
        settings,
        scope="human_email_challenge_address",
        subject=f"email:{payload.email}",
        limit=settings.email_challenge_address_limit,
        window_seconds=settings.email_challenge_rate_window_seconds,
    )
    try:
        created = create_email_challenge(
            session,
            settings,
            payload=payload,
            request_id=request.state.request_id,
        )
    except HumanSelfServiceDisabledError as exc:
        raise _self_service_disabled() from exc
    except OpenRegistrationDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "open_registration_disabled", "message": "Registration is closed"},
        ) from exc
    except EmailChallengeRateLimitedError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "email_challenge_slow_down", "message": "Try again later"},
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    except EmailDeliveryError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "email_delivery_unavailable", "message": "Email delivery failed"},
        ) from exc
    response.headers["Cache-Control"] = "no-store"
    return EmailChallengeResponse(
        challenge_id=created.challenge.challenge_id,
        expires_at=created.challenge.expires_at,
        retry_after=settings.email_challenge_cooldown_seconds,
        test_verification_code=(
            created.raw_code if settings.email_delivery_mode == "test" else None
        ),
    )


@router.post(
    "/api/v1/auth/register",
    response_model=BrowserAuthenticationResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_human(
    payload: RegistrationComplete,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
) -> BrowserAuthenticationResponse:
    try:
        user = complete_registration(
            session,
            settings,
            payload=payload,
            request_id=request.state.request_id,
        )
    except HumanSelfServiceDisabledError as exc:
        raise _self_service_disabled() from exc
    except OpenRegistrationDisabledError as exc:
        raise HTTPException(status_code=404, detail={"code": "open_registration_disabled"}) from exc
    except EmailChallengeInvalidError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "email_challenge_invalid", "message": "Code is invalid or expired"},
        ) from exc
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "email_already_registered", "message": "Email is registered"},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_password", "message": str(exc)},
        ) from exc
    created = create_human_session(
        session,
        settings,
        user=user,
        request_id=request.state.request_id,
        auth_method="email_password",
    )
    return _authentication_response(
        response,
        settings,
        user=human_profile(user),
        raw_token=created.raw_token,
        raw_csrf_token=created.raw_csrf_token,
        expires_at=created.expires_at,
        auth_method="email_password",
        mfa_authenticated=False,
    )


@router.post("/api/v1/auth/login", response_model=BrowserAuthenticationResponse)
def login_human(
    payload: HumanLogin,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
) -> BrowserAuthenticationResponse:
    if not settings.human_self_service_enabled:
        raise _self_service_disabled()
    enforce_http_rate_limit(
        request,
        session,
        settings,
        scope="human_login_ip",
        subject=client_rate_limit_subject(request),
        limit=settings.human_login_ip_limit,
        window_seconds=settings.human_login_rate_window_seconds,
    )
    enforce_http_rate_limit(
        request,
        session,
        settings,
        scope="human_login_account",
        subject=f"email:{payload.email}",
        limit=settings.human_login_account_limit,
        window_seconds=settings.human_login_rate_window_seconds,
    )
    try:
        user, mfa_authenticated = authenticate_human(
            session,
            settings,
            payload=payload,
            request_id=request.state.request_id,
        )
    except HumanSelfServiceDisabledError as exc:
        raise _self_service_disabled() from exc
    except (
        AuthenticationFailedError,
        MfaRequiredError,
        MfaInvalidError,
        PasswordNotConfiguredError,
    ) as exc:
        _raise_auth_error(exc)
    created = create_human_session(
        session,
        settings,
        user=user,
        request_id=request.state.request_id,
        auth_method="email_password",
        mfa_authenticated=mfa_authenticated,
    )
    return _authentication_response(
        response,
        settings,
        user=human_profile(user),
        raw_token=created.raw_token,
        raw_csrf_token=created.raw_csrf_token,
        expires_at=created.expires_at,
        auth_method="email_password",
        mfa_authenticated=mfa_authenticated,
    )


@router.post("/api/v1/auth/recover", response_model=BrowserAuthenticationResponse)
def complete_account_recovery(
    payload: RecoveryComplete,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
) -> BrowserAuthenticationResponse:
    try:
        user, mfa_authenticated = recover_account(
            session,
            settings,
            payload=payload,
            request_id=request.state.request_id,
        )
    except HumanSelfServiceDisabledError as exc:
        raise _self_service_disabled() from exc
    except EmailChallengeInvalidError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "email_challenge_invalid", "message": "Code is invalid or expired"},
        ) from exc
    except (MfaRequiredError, MfaInvalidError) as exc:
        _raise_auth_error(exc)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_password", "message": str(exc)},
        ) from exc
    created = create_human_session(
        session,
        settings,
        user=user,
        request_id=request.state.request_id,
        auth_method="account_recovery",
        mfa_authenticated=mfa_authenticated,
    )
    return _authentication_response(
        response,
        settings,
        user=human_profile(user),
        raw_token=created.raw_token,
        raw_csrf_token=created.raw_csrf_token,
        expires_at=created.expires_at,
        auth_method="account_recovery",
        mfa_authenticated=mfa_authenticated,
    )


@router.get("/api/v1/orbit/security", response_model=SecurityOverview)
def get_security_overview(
    session: SessionDep,
    current_human: CurrentHumanDep,
) -> SecurityOverview:
    return security_overview(session, user=current_human)


@router.post("/api/v1/orbit/security/totp/setup", response_model=TotpSetupResponse)
def start_totp_setup(
    payload: TotpSetupStart,
    session: SessionDep,
    settings: SettingsDep,
    current_human: CurrentHumanDep,
    csrf_guard: HumanCsrfDep,
) -> TotpSetupResponse:
    del csrf_guard
    try:
        secret, uri = begin_totp_setup(session, settings, user=current_human, payload=payload)
    except (
        AuthenticationFailedError,
        MfaRequiredError,
        MfaInvalidError,
        PasswordNotConfiguredError,
    ) as exc:
        _raise_auth_error(exc)
    return TotpSetupResponse(secret=secret, provisioning_uri=uri)


@router.post("/api/v1/orbit/security/totp/confirm", response_model=TotpEnabledResponse)
def complete_totp_setup(
    payload: TotpSetupConfirm,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    current_human: CurrentHumanDep,
    csrf_guard: HumanCsrfDep,
) -> TotpEnabledResponse:
    del csrf_guard
    try:
        codes = confirm_totp_setup(
            session,
            settings,
            user=current_human,
            code=payload.code,
            request_id=request.state.request_id,
        )
    except TotpInvalidStateError as exc:
        raise HTTPException(status_code=409, detail={"code": "totp_setup_not_pending"}) from exc
    except MfaInvalidError as exc:
        _raise_auth_error(exc)
    return TotpEnabledResponse(recovery_codes=codes)


@router.delete("/api/v1/orbit/security/totp", status_code=status.HTTP_204_NO_CONTENT)
def remove_totp(
    payload: PasswordMfaProof,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    current_human: CurrentHumanDep,
    csrf_guard: HumanCsrfDep,
) -> None:
    del csrf_guard
    try:
        disable_totp(
            session,
            settings,
            user=current_human,
            password=payload.password.get_secret_value(),
            totp_code=payload.totp_code,
            recovery_code=payload.recovery_code,
            request_id=request.state.request_id,
        )
    except (
        AuthenticationFailedError,
        MfaRequiredError,
        MfaInvalidError,
        PasswordNotConfiguredError,
    ) as exc:
        _raise_auth_error(exc)
    except TotpInvalidStateError as exc:
        raise HTTPException(status_code=409, detail={"code": "totp_not_enabled"}) from exc


@router.post(
    "/api/v1/orbit/security/human-keys/rotate",
    response_model=HumanKeyRotationResponse,
)
def rotate_legacy_human_key(
    payload: HumanKeyRotate,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    current_human: CurrentHumanDep,
    csrf_guard: HumanCsrfDep,
) -> HumanKeyRotationResponse:
    del csrf_guard
    try:
        rotated = rotate_human_key(
            session,
            settings,
            user=current_human,
            payload=payload,
            request_id=request.state.request_id,
        )
    except (
        AuthenticationFailedError,
        MfaRequiredError,
        MfaInvalidError,
        PasswordNotConfiguredError,
    ) as exc:
        _raise_auth_error(exc)
    response.headers["Cache-Control"] = "no-store"
    return HumanKeyRotationResponse(
        access_key=rotated.raw_key,
        key_prefix=rotated.credential.key_prefix,
        label=rotated.credential.label,
        created_at=rotated.credential.created_at,
    )
