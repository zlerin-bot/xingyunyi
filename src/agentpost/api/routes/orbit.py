from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request, Response, status
from fastapi.responses import FileResponse

from agentpost.api.dependencies import SessionDep, SettingsDep
from agentpost.control.auth import CurrentHumanDep, HumanAccessKeyDep
from agentpost.control.schemas import (
    HumanProfile,
    HumanSessionResponse,
    OrbitAgent,
    OrbitDashboard,
    OrbitMessage,
    OrbitTask,
)
from agentpost.control.service import (
    build_orbit_dashboard,
    human_profile,
    list_orbit_messages,
    list_orbit_tasks,
)
from agentpost.control.sessions import (
    HUMAN_SESSION_COOKIE,
    create_human_session,
    revoke_human_session,
)

router = APIRouter(tags=["human-control-plane"])
Limit = Annotated[int, Query(ge=1, le=200)]


def _orbit_asset(filename: str, media_type: str) -> FileResponse:
    from agentpost.orbit_ui import INDEX_PATH

    return FileResponse(
        INDEX_PATH.with_name(filename),
        media_type=media_type,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/orbit", include_in_schema=False)
def orbit_console() -> FileResponse:
    from agentpost.orbit_ui import INDEX_PATH

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


@router.get("/", include_in_schema=False)
def platform_home() -> FileResponse:
    return orbit_console()


@router.get("/orbit/styles.css", include_in_schema=False)
def orbit_styles() -> FileResponse:
    return _orbit_asset("styles.css", "text/css")


@router.get("/orbit/app.js", include_in_schema=False)
def orbit_script() -> FileResponse:
    return _orbit_asset("app.js", "text/javascript")


@router.get("/api/v1/orbit/me", response_model=HumanProfile)
def orbit_me(current_human: CurrentHumanDep) -> HumanProfile:
    return human_profile(current_human)


@router.post(
    "/api/v1/orbit/session",
    response_model=HumanSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_orbit_session(
    response: Response,
    request: Request,
    access_key_user: HumanAccessKeyDep,
    session: SessionDep,
    settings: SettingsDep,
) -> HumanSessionResponse:
    created = create_human_session(
        session,
        settings,
        user=access_key_user,
        request_id=request.state.request_id,
    )
    response.set_cookie(
        key=HUMAN_SESSION_COOKIE,
        value=created.raw_token,
        max_age=settings.human_session_ttl_seconds,
        path="/api/v1/orbit",
        secure=settings.is_production,
        httponly=True,
        samesite="strict",
    )
    return HumanSessionResponse(
        user=human_profile(access_key_user),
        expires_at=created.expires_at,
    )


@router.delete(
    "/api/v1/orbit/session",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_orbit_session(
    response: Response,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> None:
    raw_session = request.cookies.get(HUMAN_SESSION_COOKIE, "")
    if raw_session:
        revoke_human_session(
            session,
            settings,
            raw_token=raw_session,
            request_id=request.state.request_id,
        )
    response.delete_cookie(
        key=HUMAN_SESSION_COOKIE,
        path="/api/v1/orbit",
        secure=settings.is_production,
        httponly=True,
        samesite="strict",
    )


@router.get("/api/v1/orbit/dashboard", response_model=OrbitDashboard)
def orbit_dashboard(
    current_human: CurrentHumanDep,
    session: SessionDep,
) -> OrbitDashboard:
    return build_orbit_dashboard(session, current_human)


@router.get("/api/v1/orbit/agents", response_model=list[OrbitAgent])
def orbit_agents(
    current_human: CurrentHumanDep,
    session: SessionDep,
) -> list[OrbitAgent]:
    return build_orbit_dashboard(session, current_human).agents


@router.get("/api/v1/orbit/messages", response_model=list[OrbitMessage])
def orbit_messages(
    current_human: CurrentHumanDep,
    session: SessionDep,
    limit: Limit = 50,
) -> list[OrbitMessage]:
    return list_orbit_messages(session, current_human, limit=limit)


@router.get("/api/v1/orbit/tasks", response_model=list[OrbitTask])
def orbit_tasks(
    current_human: CurrentHumanDep,
    session: SessionDep,
    limit: Limit = 50,
) -> list[OrbitTask]:
    return list_orbit_tasks(session, current_human, limit=limit)
