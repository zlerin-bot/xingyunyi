from __future__ import annotations

from typing import Annotated
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Form, Query, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse

from agentpost.api.dependencies import CurrentAgentDep, SessionDep, SettingsDep
from agentpost.control.auth import CurrentHumanDep
from agentpost.control.human_security import HumanCsrfDep
from agentpost.oauth.constants import DEVICE_GRANT_TYPE, MESSAGING_SCOPE
from agentpost.oauth.schemas import (
    DeviceAuthorizationResponse,
    OAuthClientRegistrationRequest,
    OAuthClientRegistrationResponse,
    OAuthTokenInfo,
    OAuthTokenResponse,
)
from agentpost.oauth.service import (
    OAuthAccessDeniedError,
    OAuthAuthorizationNotReadyError,
    OAuthAuthorizationPendingError,
    OAuthDisabledError,
    OAuthExpiredTokenError,
    OAuthInvalidClientError,
    OAuthInvalidGrantError,
    OAuthInvalidRedirectUriError,
    OAuthInvalidRequestError,
    OAuthInvalidScopeError,
    OAuthInvalidTargetError,
    OAuthSlowDownError,
    complete_authorization_code,
    create_device_authorization,
    exchange_authorization_code,
    exchange_device_code,
    oauth_resource,
    refresh_access_token,
    register_dynamic_client,
    start_authorization_code,
)
from agentpost.security.rate_limit import client_rate_limit_subject, enforce_http_rate_limit

router = APIRouter(tags=["oauth"])
REFRESH_GRANT_TYPE = "refresh_token"
AUTHORIZATION_CODE_GRANT_TYPE = "authorization_code"


def _oauth_error(
    error: str,
    description: str,
    *,
    status_code: int = status.HTTP_400_BAD_REQUEST,
    retry_after: int | None = None,
) -> JSONResponse:
    headers = {"Cache-Control": "no-store", "Pragma": "no-cache"}
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return JSONResponse(
        status_code=status_code,
        content={"error": error, "error_description": description},
        headers=headers,
    )


@router.get("/.well-known/oauth-authorization-server")
def oauth_authorization_server_metadata(settings: SettingsDep) -> dict[str, object]:
    return {
        "issuer": settings.public_base_url,
        "authorization_endpoint": f"{settings.public_base_url}/oauth/authorize",
        "device_authorization_endpoint": f"{settings.public_base_url}/oauth/device_authorization",
        "token_endpoint": f"{settings.public_base_url}/oauth/token",
        "registration_endpoint": f"{settings.public_base_url}/oauth/register",
        "grant_types_supported": [
            AUTHORIZATION_CODE_GRANT_TYPE,
            DEVICE_GRANT_TYPE,
            REFRESH_GRANT_TYPE,
        ],
        "response_types_supported": ["code"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "scopes_supported": [MESSAGING_SCOPE],
    }


@router.get("/.well-known/oauth-protected-resource")
def oauth_protected_resource_metadata(settings: SettingsDep) -> dict[str, object]:
    return {
        "resource": oauth_resource(settings),
        "authorization_servers": [settings.public_base_url],
        "scopes_supported": [MESSAGING_SCOPE],
        "bearer_methods_supported": ["header"],
    }


@router.get("/.well-known/oauth-protected-resource/mcp/connect/{intent}", response_model=None)
def oauth_intent_protected_resource_metadata(
    intent: str,
    settings: SettingsDep,
) -> dict[str, object] | JSONResponse:
    try:
        prefix, raw_id = intent.split("-", maxsplit=1)
        valid_intent = prefix in {"new", "agent"} and len(raw_id) == 36
    except ValueError:
        valid_intent = False
    if not valid_intent:
        return _oauth_error("invalid_target", "The requested resource is not supported")
    return {
        "resource": f"{oauth_resource(settings).rstrip('/')}/connect/{intent}",
        "authorization_servers": [settings.public_base_url],
        "scopes_supported": [MESSAGING_SCOPE],
        "bearer_methods_supported": ["header"],
    }


@router.post(
    "/oauth/register",
    response_model=OAuthClientRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def oauth_register_client(
    payload: OAuthClientRegistrationRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
) -> OAuthClientRegistrationResponse | JSONResponse:
    enforce_http_rate_limit(
        request,
        session,
        settings,
        scope="oauth_dynamic_client_ip",
        subject=client_rate_limit_subject(request),
        limit=settings.pairing_create_ip_limit,
        window_seconds=settings.pairing_rate_window_seconds,
    )
    try:
        client = register_dynamic_client(session, settings, payload=payload)
    except OAuthDisabledError:
        return _oauth_error(
            "temporarily_unavailable",
            "Remote MCP OAuth is unavailable",
            status_code=404,
        )
    except OAuthInvalidRedirectUriError:
        return _oauth_error("invalid_redirect_uri", "A redirect URI is not allowed")
    except OAuthInvalidScopeError:
        return _oauth_error("invalid_scope", "The requested scope is not supported")
    except OAuthInvalidRequestError:
        return _oauth_error("invalid_client_metadata", "The client metadata is not supported")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return OAuthClientRegistrationResponse(
        client_id=client.client_id,
        client_id_issued_at=int(client.created_at.timestamp()),
        client_name=client.client_name,
        redirect_uris=list(client.redirect_uris),
        grant_types=list(client.grant_types),
        response_types=list(client.response_types),
    )


@router.get("/oauth/authorize", response_model=None)
def oauth_authorize(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    client_id: str = Query(min_length=1, max_length=96),
    redirect_uri: str = Query(min_length=1, max_length=1000),
    response_type: str = Query(min_length=1, max_length=32),
    code_challenge: str = Query(min_length=43, max_length=128),
    code_challenge_method: str = Query(min_length=1, max_length=16),
    resource: str = Query(min_length=1, max_length=1000),
    scope: str = Query(default=MESSAGING_SCOPE, min_length=1, max_length=1000),
    state: str | None = Query(default=None, max_length=2000),
) -> RedirectResponse | JSONResponse:
    enforce_http_rate_limit(
        request,
        session,
        settings,
        scope="oauth_authorize_ip",
        subject=client_rate_limit_subject(request),
        limit=settings.pairing_create_ip_limit,
        window_seconds=settings.pairing_rate_window_seconds,
    )
    try:
        started = start_authorization_code(
            session,
            settings,
            client_id=client_id,
            redirect_uri=redirect_uri,
            response_type=response_type,
            scope=scope,
            resource=resource,
            state=state,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            request_id=request.state.request_id,
        )
    except OAuthDisabledError:
        return _oauth_error(
            "temporarily_unavailable",
            "Remote MCP OAuth is unavailable",
            status_code=404,
        )
    except OAuthInvalidClientError:
        return _oauth_error("invalid_client", "The OAuth client is not allowed", status_code=401)
    except OAuthInvalidRedirectUriError:
        return _oauth_error("invalid_request", "The redirect URI is not registered")
    except OAuthInvalidScopeError:
        return _oauth_error("invalid_scope", "The requested scope is not supported")
    except OAuthInvalidTargetError:
        return _oauth_error("invalid_target", "The requested resource is not supported")
    except OAuthInvalidRequestError:
        return _oauth_error("invalid_request", "The authorization request is not supported")
    orbit = f"{settings.public_base_url}/orbit"
    query = urlencode(
        {
            "pairing": started.pairing.pairing_id,
            "code": started.user_code,
            "oauth_request": started.authorization_request.request_id,
        }
    )
    return RedirectResponse(f"{orbit}?{query}", status_code=status.HTTP_302_FOUND)


def _redirect_with_oauth_result(
    redirect_uri: str,
    *,
    state_value: str | None,
    code: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    parsed = urlsplit(redirect_uri)
    query = list(parse_qsl(parsed.query, keep_blank_values=True))
    if code is not None:
        query.append(("code", code))
    if error is not None:
        query.append(("error", error))
    if state_value is not None:
        query.append(("state", state_value))
    target = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), ""))
    return RedirectResponse(target, status_code=status.HTTP_302_FOUND)


@router.post("/api/v1/orbit/oauth/authorize/complete", response_model=None)
def oauth_authorize_complete(
    authorization_request: str,
    current_human: CurrentHumanDep,
    csrf_guard: HumanCsrfDep,
    session: SessionDep,
    settings: SettingsDep,
) -> JSONResponse:
    del csrf_guard
    try:
        completed = complete_authorization_code(
            session,
            settings,
            authorization_request_id=authorization_request,
            human_user_id=current_human.id,
        )
    except OAuthExpiredTokenError:
        return _oauth_error("expired_token", "The authorization request has expired")
    except OAuthAuthorizationNotReadyError:
        return _oauth_error("authorization_pending", "The Human decision is not complete")
    except OAuthInvalidRequestError:
        return _oauth_error("invalid_request", "The authorization request is invalid")
    redirect = _redirect_with_oauth_result(
        completed.authorization_request.redirect_uri,
        state_value=completed.authorization_request.state,
        code=completed.code,
        error=completed.error,
    )
    return JSONResponse(
        {"redirect_to": redirect.headers["location"]},
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )


@router.post("/oauth/device_authorization", response_model=DeviceAuthorizationResponse)
def oauth_device_authorization(
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    client_id: Annotated[str, Form(min_length=1, max_length=255)],
    scope: Annotated[str, Form(min_length=1, max_length=1000)] = MESSAGING_SCOPE,
    resource: Annotated[str | None, Form(max_length=1000)] = None,
) -> DeviceAuthorizationResponse | JSONResponse:
    try:
        created = create_device_authorization(
            session,
            settings,
            client_id=client_id,
            scope=scope,
            resource=resource,
            request_id=request.state.request_id,
        )
    except OAuthDisabledError:
        return _oauth_error(
            "temporarily_unavailable",
            "Remote MCP OAuth is unavailable",
            status_code=404,
        )
    except OAuthInvalidClientError:
        return _oauth_error("invalid_client", "The OAuth client is not allowed", status_code=401)
    except OAuthInvalidScopeError:
        return _oauth_error("invalid_scope", "The requested scope is not supported")
    except OAuthInvalidTargetError:
        return _oauth_error("invalid_target", "The requested resource is not supported")
    verification_uri = f"{settings.public_base_url}/orbit"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return DeviceAuthorizationResponse(
        device_code=created.device_code,
        user_code=created.user_code,
        verification_uri=verification_uri,
        verification_uri_complete=(
            f"{verification_uri}?pairing={quote(created.pairing.pairing_id)}"
            f"&code={quote(created.user_code)}"
        ),
        expires_in=settings.pairing_ttl_seconds,
        interval=settings.pairing_poll_interval_seconds,
    )


@router.post("/oauth/token", response_model=OAuthTokenResponse)
def oauth_token(
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    grant_type: Annotated[str, Form(min_length=1, max_length=200)],
    client_id: Annotated[str, Form(min_length=1, max_length=255)],
    device_code: Annotated[str | None, Form(min_length=20, max_length=256)] = None,
    refresh_token: Annotated[str | None, Form(min_length=20, max_length=256)] = None,
    code: Annotated[str | None, Form(min_length=20, max_length=256)] = None,
    redirect_uri: Annotated[str | None, Form(min_length=1, max_length=1000)] = None,
    code_verifier: Annotated[str | None, Form(min_length=43, max_length=128)] = None,
    resource: Annotated[str | None, Form(min_length=1, max_length=1000)] = None,
) -> OAuthTokenResponse | JSONResponse:
    try:
        if (
            grant_type == DEVICE_GRANT_TYPE
            and device_code is not None
            and refresh_token is None
            and code is None
        ):
            result = exchange_device_code(
                session,
                settings,
                client_id=client_id,
                device_code=device_code,
                request_id=request.state.request_id,
            )
        elif (
            grant_type == AUTHORIZATION_CODE_GRANT_TYPE
            and code is not None
            and redirect_uri is not None
            and code_verifier is not None
            and device_code is None
            and refresh_token is None
        ):
            result = exchange_authorization_code(
                session,
                settings,
                client_id=client_id,
                raw_code=code,
                redirect_uri=redirect_uri,
                code_verifier=code_verifier,
                resource=resource,
                request_id=request.state.request_id,
            )
        elif (
            grant_type == REFRESH_GRANT_TYPE
            and refresh_token is not None
            and device_code is None
            and code is None
        ):
            result = refresh_access_token(
                session,
                settings,
                client_id=client_id,
                raw_refresh_token=refresh_token,
                request_id=request.state.request_id,
            )
        else:
            return _oauth_error("unsupported_grant_type", "The grant request is not supported")
    except OAuthDisabledError:
        return _oauth_error(
            "temporarily_unavailable",
            "Remote MCP OAuth is unavailable",
            status_code=404,
        )
    except OAuthInvalidClientError:
        return _oauth_error("invalid_client", "The OAuth client is not allowed", status_code=401)
    except OAuthInvalidTargetError:
        return _oauth_error("invalid_target", "The requested resource is not supported")
    except OAuthAuthorizationPendingError:
        return _oauth_error("authorization_pending", "The Human has not completed authorization")
    except OAuthSlowDownError as exc:
        return _oauth_error("slow_down", "Polling is too frequent", retry_after=exc.retry_after)
    except OAuthAccessDeniedError:
        return _oauth_error("access_denied", "The Human denied authorization")
    except OAuthExpiredTokenError:
        return _oauth_error("expired_token", "The device authorization expired")
    except OAuthInvalidGrantError:
        return _oauth_error("invalid_grant", "The OAuth grant is invalid or revoked")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return result


@router.get("/api/v1/oauth/token-info", response_model=OAuthTokenInfo)
def oauth_token_info(
    request: Request,
    response: Response,
    current_agent: CurrentAgentDep,
) -> OAuthTokenInfo | JSONResponse:
    if getattr(request.state, "agent_credential_kind", None) != "oauth_access":
        return _oauth_error("invalid_token", "An OAuth access token is required", status_code=401)
    expires_at = request.state.oauth_expires_at
    response.headers["Cache-Control"] = "no-store"
    return OAuthTokenInfo(
        client_id=request.state.oauth_client_id,
        scope=request.state.oauth_scope,
        resource=request.state.oauth_resource,
        sub=current_agent.id,
        connector_id=request.state.connector_instance_id,
        exp=int(expires_at.timestamp()),
    )
