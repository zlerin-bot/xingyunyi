from __future__ import annotations

from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Form, Request, Response, status
from fastapi.responses import JSONResponse

from agentpost.api.dependencies import CurrentAgentDep, SessionDep, SettingsDep
from agentpost.oauth.constants import DEVICE_GRANT_TYPE, MESSAGING_SCOPE
from agentpost.oauth.schemas import DeviceAuthorizationResponse, OAuthTokenInfo, OAuthTokenResponse
from agentpost.oauth.service import (
    OAuthAccessDeniedError,
    OAuthAuthorizationPendingError,
    OAuthDisabledError,
    OAuthExpiredTokenError,
    OAuthInvalidClientError,
    OAuthInvalidGrantError,
    OAuthInvalidScopeError,
    OAuthInvalidTargetError,
    OAuthSlowDownError,
    create_device_authorization,
    exchange_device_code,
    oauth_resource,
    refresh_access_token,
)

router = APIRouter(tags=["oauth"])
REFRESH_GRANT_TYPE = "refresh_token"


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
        "device_authorization_endpoint": f"{settings.public_base_url}/oauth/device_authorization",
        "token_endpoint": f"{settings.public_base_url}/oauth/token",
        "grant_types_supported": [DEVICE_GRANT_TYPE, REFRESH_GRANT_TYPE],
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
) -> OAuthTokenResponse | JSONResponse:
    try:
        if grant_type == DEVICE_GRANT_TYPE and device_code is not None and refresh_token is None:
            result = exchange_device_code(
                session,
                settings,
                client_id=client_id,
                device_code=device_code,
                request_id=request.state.request_id,
            )
        elif grant_type == REFRESH_GRANT_TYPE and refresh_token is not None and device_code is None:
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
