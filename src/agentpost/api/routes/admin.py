from __future__ import annotations

import hashlib
import secrets
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from agentpost.admin.service import (
    list_agents,
    list_audit_logs,
    list_deliveries,
    list_messages,
    list_threads,
)
from agentpost.api.dependencies import SessionDep, SettingsDep

router = APIRouter(tags=["admin"])
_bearer = HTTPBearer(auto_error=False)


def _admin_denied() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "not_found", "message": "Resource was not found"},
    )


def require_admin(
    request: Request,
    settings: SettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> None:
    configured = settings.admin_token
    if configured is None or credentials is None or credentials.scheme.casefold() != "bearer":
        raise _admin_denied()
    supplied = credentials.credentials
    expected = configured.get_secret_value()
    candidate = supplied if 1 <= len(supplied) <= 512 else ""
    supplied_digest = hashlib.sha256(candidate.encode("utf-8")).digest()
    expected_digest = hashlib.sha256(expected.encode("utf-8")).digest()
    if not candidate or not secrets.compare_digest(supplied_digest, expected_digest):
        raise _admin_denied()
    request.state.admin_authenticated = True


AdminDep = Annotated[None, Depends(require_admin)]
Limit = Annotated[int, Query(ge=1, le=200)]


@router.get("/admin", include_in_schema=False)
def admin_console(settings: SettingsDep) -> FileResponse:
    if settings.admin_token is None:
        raise _admin_denied()
    from agentpost.admin_ui import INDEX_PATH

    return FileResponse(
        INDEX_PATH,
        media_type="text/html",
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": (
                "default-src 'none'; style-src 'self'; script-src 'self'; "
                "connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
            ),
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
        },
    )


def _admin_asset(settings: SettingsDep, filename: str, media_type: str) -> FileResponse:
    if settings.admin_token is None:
        raise _admin_denied()
    from agentpost.admin_ui import INDEX_PATH

    return FileResponse(
        INDEX_PATH.with_name(filename),
        media_type=media_type,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/admin/styles.css", include_in_schema=False)
def admin_styles(settings: SettingsDep) -> FileResponse:
    return _admin_asset(settings, "styles.css", "text/css")


@router.get("/admin/app.js", include_in_schema=False)
def admin_script(settings: SettingsDep) -> FileResponse:
    return _admin_asset(settings, "app.js", "text/javascript")


@router.get("/api/v1/admin/agents")
def admin_agents(_: AdminDep, session: SessionDep, limit: Limit = 50) -> dict[str, Any]:
    return {"items": list_agents(session, limit=limit)}


@router.get("/api/v1/admin/messages")
def admin_messages(_: AdminDep, session: SessionDep, limit: Limit = 50) -> dict[str, Any]:
    return {"items": list_messages(session, limit=limit)}


@router.get("/api/v1/admin/threads")
def admin_threads(_: AdminDep, session: SessionDep, limit: Limit = 50) -> dict[str, Any]:
    return {"items": list_threads(session, limit=limit)}


@router.get("/api/v1/admin/deliveries")
def admin_deliveries(_: AdminDep, session: SessionDep, limit: Limit = 50) -> dict[str, Any]:
    return {"items": list_deliveries(session, limit=limit)}


@router.get("/api/v1/admin/audit-logs")
def admin_audit_logs(_: AdminDep, session: SessionDep, limit: Limit = 50) -> dict[str, Any]:
    return {"items": list_audit_logs(session, limit=limit)}
