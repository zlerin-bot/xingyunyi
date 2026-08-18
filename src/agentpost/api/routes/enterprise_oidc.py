from __future__ import annotations

from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse

from agentpost.accounts.service import (
    AuthenticationFailedError,
    MfaInvalidError,
    MfaRequiredError,
    PasswordNotConfiguredError,
)
from agentpost.api.dependencies import SessionDep, SettingsDep
from agentpost.control.auth import CurrentHumanDep
from agentpost.control.human_security import HumanCsrfDep, human_session_id_from_request
from agentpost.control.sessions import HUMAN_SESSION_COOKIE, create_human_session
from agentpost.sso.schemas import (
    OidcLinkStart,
    OidcLoginStartResponse,
    OidcProviderCreate,
    OidcProviderDiscoveryRequest,
    OidcProviderResponse,
)
from agentpost.sso.service import (
    OidcAccessDeniedError,
    OidcAccountLinkRequiredError,
    OidcClaimsInvalidError,
    OidcDisabledError,
    OidcIssuerNotAllowedError,
    OidcProviderConfigurationError,
    OidcProviderConflictError,
    OidcProviderNotFoundError,
    OidcStateInvalidError,
    OidcTokenExchangeError,
    OidcVerifiedDomainRequiredError,
    complete_login,
    create_provider,
    disable_provider,
    discover_providers,
    list_providers,
    start_account_link,
    start_login,
)

router = APIRouter(tags=["enterprise-oidc"])


def _disabled() -> HTTPException:
    return HTTPException(status_code=404, detail={"code": "enterprise_oidc_disabled"})


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={"code": "oidc_provider_not_found"})


def _transport(request: Request) -> httpx.BaseTransport | None:
    value = getattr(request.app.state, "oidc_http_transport", None)
    return value if isinstance(value, httpx.BaseTransport) else None


@router.post(
    "/api/v1/orbit/organizations/{organization_id}/oidc-providers",
    response_model=OidcProviderResponse,
    status_code=status.HTTP_201_CREATED,
)
def configure_oidc_provider(
    organization_id: UUID,
    payload: OidcProviderCreate,
    request: Request,
    current_human: CurrentHumanDep,
    session: SessionDep,
    settings: SettingsDep,
    csrf_guard: HumanCsrfDep,
) -> OidcProviderResponse:
    del csrf_guard
    try:
        return create_provider(
            session,
            settings,
            organization_id=organization_id,
            user=current_human,
            payload=payload,
            human_session_id=human_session_id_from_request(request),
            request_id=request.state.request_id,
            transport=_transport(request),
        )
    except OidcDisabledError as exc:
        raise _disabled() from exc
    except OidcProviderNotFoundError as exc:
        raise _not_found() from exc
    except OidcAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail={"code": "oidc_management_forbidden"}) from exc
    except OidcVerifiedDomainRequiredError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "verified_organization_domain_required"},
        ) from exc
    except OidcIssuerNotAllowedError as exc:
        raise HTTPException(status_code=422, detail={"code": "oidc_issuer_not_allowed"}) from exc
    except OidcProviderConflictError as exc:
        raise HTTPException(status_code=409, detail={"code": "oidc_provider_conflict"}) from exc
    except OidcProviderConfigurationError as exc:
        session.rollback()
        raise HTTPException(
            status_code=422,
            detail={"code": "oidc_provider_configuration_invalid"},
        ) from exc


@router.get(
    "/api/v1/orbit/organizations/{organization_id}/oidc-providers",
    response_model=dict[str, list[OidcProviderResponse]],
)
def get_oidc_providers(
    organization_id: UUID,
    current_human: CurrentHumanDep,
    session: SessionDep,
    settings: SettingsDep,
) -> dict[str, list[OidcProviderResponse]]:
    try:
        return {
            "items": list_providers(
                session,
                settings,
                organization_id=organization_id,
                user=current_human,
            )
        }
    except OidcDisabledError as exc:
        raise _disabled() from exc
    except OidcProviderNotFoundError as exc:
        raise _not_found() from exc
    except OidcAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail={"code": "oidc_management_forbidden"}) from exc


@router.delete(
    "/api/v1/orbit/organizations/{organization_id}/oidc-providers/{provider_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_oidc_provider(
    organization_id: UUID,
    provider_id: UUID,
    request: Request,
    current_human: CurrentHumanDep,
    session: SessionDep,
    settings: SettingsDep,
    csrf_guard: HumanCsrfDep,
) -> None:
    del csrf_guard
    try:
        disable_provider(
            session,
            settings,
            organization_id=organization_id,
            provider_id=provider_id,
            user=current_human,
            human_session_id=human_session_id_from_request(request),
            request_id=request.state.request_id,
        )
    except OidcDisabledError as exc:
        raise _disabled() from exc
    except OidcProviderNotFoundError as exc:
        raise _not_found() from exc
    except OidcAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail={"code": "oidc_management_forbidden"}) from exc


@router.post(
    "/api/v1/auth/oidc/providers",
    response_model=dict[str, list[OidcProviderResponse]],
)
def find_oidc_providers(
    payload: OidcProviderDiscoveryRequest,
    session: SessionDep,
    settings: SettingsDep,
) -> dict[str, list[OidcProviderResponse]]:
    try:
        return {"items": discover_providers(session, settings, email=payload.email)}
    except OidcDisabledError as exc:
        raise _disabled() from exc


@router.post(
    "/api/v1/auth/oidc/{provider_id}/start",
    response_model=OidcLoginStartResponse,
)
def begin_oidc_login(
    provider_id: UUID,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> OidcLoginStartResponse:
    try:
        return start_login(
            session,
            settings,
            provider_id=provider_id,
            request_id=request.state.request_id,
        )
    except OidcDisabledError as exc:
        raise _disabled() from exc
    except OidcProviderNotFoundError as exc:
        raise _not_found() from exc


@router.post(
    "/api/v1/orbit/organizations/{organization_id}/oidc-providers/{provider_id}/link",
    response_model=OidcLoginStartResponse,
)
def begin_oidc_account_link(
    organization_id: UUID,
    provider_id: UUID,
    payload: OidcLinkStart,
    request: Request,
    current_human: CurrentHumanDep,
    session: SessionDep,
    settings: SettingsDep,
    csrf_guard: HumanCsrfDep,
) -> OidcLoginStartResponse:
    del csrf_guard
    try:
        return start_account_link(
            session,
            settings,
            organization_id=organization_id,
            provider_id=provider_id,
            user=current_human,
            proof=payload,
            request_id=request.state.request_id,
        )
    except OidcDisabledError as exc:
        raise _disabled() from exc
    except OidcProviderNotFoundError as exc:
        raise _not_found() from exc
    except MfaRequiredError as exc:
        raise HTTPException(status_code=409, detail={"code": "mfa_required"}) from exc
    except (AuthenticationFailedError, MfaInvalidError, PasswordNotConfiguredError) as exc:
        raise HTTPException(status_code=401, detail={"code": "reauthentication_failed"}) from exc


@router.get("/api/v1/auth/oidc/callback", response_class=RedirectResponse)
def finish_oidc_login(
    response: Response,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    code: str = Query(min_length=1, max_length=4000),
    state_value: str = Query(alias="state", min_length=20, max_length=512),
) -> RedirectResponse:
    del response
    try:
        authenticated = complete_login(
            session,
            settings,
            raw_state=state_value,
            code=code,
            request_id=request.state.request_id,
            transport=_transport(request),
        )
    except OidcDisabledError as exc:
        raise _disabled() from exc
    except OidcStateInvalidError as exc:
        raise HTTPException(status_code=400, detail={"code": "oidc_state_invalid"}) from exc
    except OidcTokenExchangeError as exc:
        raise HTTPException(status_code=502, detail={"code": "oidc_exchange_failed"}) from exc
    except OidcClaimsInvalidError as exc:
        raise HTTPException(status_code=401, detail={"code": "oidc_claims_invalid"}) from exc
    except OidcAccountLinkRequiredError as exc:
        raise HTTPException(status_code=409, detail={"code": "oidc_account_link_required"}) from exc
    except OidcAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail={"code": "oidc_membership_required"}) from exc
    created = create_human_session(
        session,
        settings,
        user=authenticated.user,
        request_id=request.state.request_id,
        auth_method="enterprise_oidc",
        mfa_authenticated=authenticated.mfa_authenticated,
    )
    redirect = RedirectResponse(url="/orbit?oidc=success", status_code=status.HTTP_303_SEE_OTHER)
    redirect.set_cookie(
        key=HUMAN_SESSION_COOKIE,
        value=created.raw_token,
        max_age=settings.human_session_ttl_seconds,
        path="/api/v1/orbit",
        secure=settings.is_production,
        httponly=True,
        samesite="strict",
    )
    redirect.headers["Cache-Control"] = "no-store"
    return redirect
