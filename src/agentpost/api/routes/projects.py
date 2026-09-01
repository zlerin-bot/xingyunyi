from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, Response, status

from agentpost.api.dependencies import SessionDep
from agentpost.control.auth import CurrentHumanDep
from agentpost.control.human_security import HumanCsrfDep, human_session_id_from_request
from agentpost.projects.schemas import (
    FriendResponse,
    ProjectCreate,
    ProjectDetail,
    ProjectMembersInvite,
    ProjectStatusUpdate,
    ProjectSummary,
)
from agentpost.projects.service import (
    ProjectFriendRequiredError,
    ProjectMembershipConflictError,
    ProjectNotFoundError,
    ProjectOwnerRequiredError,
    create_project,
    decide_project_invitation,
    get_project,
    invite_project_members,
    list_friends,
    list_project_invitation_candidates,
    update_project_status,
)
from agentpost.projects.service import (
    list_projects as list_human_projects,
)

router = APIRouter(prefix="/api/v1/orbit", tags=["projects"])
Limit = Annotated[int, Query(ge=1, le=200)]


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "project_not_found", "message": "Project was not found"},
    )


def _forbidden() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "project_owner_required", "message": "Project owner access is required"},
    )


def _conflict() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": "project_membership_conflict", "message": "Project state has changed"},
    )


@router.get("/friends", response_model=dict[str, list[FriendResponse]])
def get_friends(
    current_human: CurrentHumanDep,
    session: SessionDep,
    query: Annotated[str | None, Query(max_length=100)] = None,
    limit: Limit = 100,
) -> dict[str, list[FriendResponse]]:
    return {"items": list_friends(session, user=current_human, query=query, limit=limit)}


@router.get("/projects", response_model=dict[str, list[ProjectSummary]])
def get_projects(
    current_human: CurrentHumanDep,
    session: SessionDep,
    limit: Limit = 100,
) -> dict[str, list[ProjectSummary]]:
    return {"items": list_human_projects(session, user=current_human, limit=limit)}


@router.post("/projects", response_model=ProjectDetail, status_code=status.HTTP_201_CREATED)
def create_human_project(
    payload: ProjectCreate,
    request: Request,
    current_human: CurrentHumanDep,
    session: SessionDep,
    csrf_guard: HumanCsrfDep,
) -> ProjectDetail:
    del csrf_guard
    return create_project(
        session,
        user=current_human,
        payload=payload,
        human_session_id=human_session_id_from_request(request),
        request_id=request.state.request_id,
    )


@router.get("/projects/{project_id}", response_model=ProjectDetail)
def get_human_project(
    project_id: UUID,
    current_human: CurrentHumanDep,
    session: SessionDep,
) -> ProjectDetail:
    try:
        return get_project(session, user=current_human, project_id=project_id)
    except ProjectNotFoundError as exc:
        raise _not_found() from exc


@router.get(
    "/projects/{project_id}/invite-candidates",
    response_model=dict[str, list[FriendResponse]],
)
def get_project_invitation_candidates(
    project_id: UUID,
    current_human: CurrentHumanDep,
    session: SessionDep,
    limit: Limit = 100,
) -> dict[str, list[FriendResponse]]:
    try:
        return {
            "items": list_project_invitation_candidates(
                session,
                user=current_human,
                project_id=project_id,
                limit=limit,
            )
        }
    except ProjectNotFoundError as exc:
        raise _not_found() from exc
    except ProjectOwnerRequiredError as exc:
        raise _forbidden() from exc


@router.post("/projects/{project_id}/members", response_model=ProjectDetail)
def invite_human_project_members(
    project_id: UUID,
    payload: ProjectMembersInvite,
    request: Request,
    current_human: CurrentHumanDep,
    session: SessionDep,
    csrf_guard: HumanCsrfDep,
) -> ProjectDetail:
    del csrf_guard
    try:
        return invite_project_members(
            session,
            user=current_human,
            project_id=project_id,
            human_user_ids=payload.human_user_ids,
            human_session_id=human_session_id_from_request(request),
            request_id=request.state.request_id,
        )
    except (ProjectNotFoundError, ProjectFriendRequiredError) as exc:
        raise _not_found() from exc
    except ProjectOwnerRequiredError as exc:
        raise _forbidden() from exc
    except ProjectMembershipConflictError as exc:
        raise _conflict() from exc


@router.post("/projects/{project_id}/accept", response_model=ProjectDetail)
def accept_human_project_invitation(
    project_id: UUID,
    request: Request,
    current_human: CurrentHumanDep,
    session: SessionDep,
    csrf_guard: HumanCsrfDep,
) -> ProjectDetail:
    del csrf_guard
    try:
        result = decide_project_invitation(
            session,
            user=current_human,
            project_id=project_id,
            accept=True,
            human_session_id=human_session_id_from_request(request),
            request_id=request.state.request_id,
        )
    except ProjectNotFoundError as exc:
        raise _not_found() from exc
    except ProjectMembershipConflictError as exc:
        raise _conflict() from exc
    assert result is not None
    return result


@router.post("/projects/{project_id}/decline", status_code=status.HTTP_204_NO_CONTENT)
def decline_human_project_invitation(
    project_id: UUID,
    request: Request,
    current_human: CurrentHumanDep,
    session: SessionDep,
    csrf_guard: HumanCsrfDep,
) -> Response:
    del csrf_guard
    try:
        decide_project_invitation(
            session,
            user=current_human,
            project_id=project_id,
            accept=False,
            human_session_id=human_session_id_from_request(request),
            request_id=request.state.request_id,
        )
    except ProjectNotFoundError as exc:
        raise _not_found() from exc
    except ProjectMembershipConflictError as exc:
        raise _conflict() from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/projects/{project_id}/status", response_model=ProjectDetail)
def change_human_project_status(
    project_id: UUID,
    payload: ProjectStatusUpdate,
    request: Request,
    current_human: CurrentHumanDep,
    session: SessionDep,
    csrf_guard: HumanCsrfDep,
) -> ProjectDetail:
    del csrf_guard
    try:
        return update_project_status(
            session,
            user=current_human,
            project_id=project_id,
            status=payload.status,
            human_session_id=human_session_id_from_request(request),
            request_id=request.state.request_id,
        )
    except ProjectNotFoundError as exc:
        raise _not_found() from exc
    except ProjectOwnerRequiredError as exc:
        raise _forbidden() from exc
    except ProjectMembershipConflictError as exc:
        raise _conflict() from exc
