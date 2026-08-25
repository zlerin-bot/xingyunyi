from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from agentpost.api.dependencies import CurrentAgentDep, SessionDep
from agentpost.directory.schemas import (
    DirectorySearchResponse,
    RecipientResolution,
    RecipientResolveRequest,
)
from agentpost.directory.service import (
    MAX_CAPABILITY_LENGTH,
    MAX_QUERY_LENGTH,
    DirectoryFilters,
    InvalidDirectoryFilterError,
    resolve_recipient,
    search_directory,
)

router = APIRouter(prefix="/api/v1/directory", tags=["directory"])


@router.post("/resolve", response_model=RecipientResolution)
def resolve_agent_recipient(
    payload: RecipientResolveRequest,
    session: SessionDep,
    current_agent: CurrentAgentDep,
) -> RecipientResolution:
    return resolve_recipient(session, caller=current_agent, query=payload.query)


@router.get("/search", response_model=DirectorySearchResponse)
def search_agents(
    session: SessionDep,
    current_agent: CurrentAgentDep,
    q: Annotated[str | None, Query(max_length=MAX_QUERY_LENGTH)] = None,
    capability: Annotated[
        str | None,
        Query(max_length=MAX_CAPABILITY_LENGTH),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> DirectorySearchResponse:
    # Resolving the authenticated agent is the authorization boundary even though
    # discovery results are not personalized in the MVP.
    _ = current_agent
    try:
        filters = DirectoryFilters.normalize(q=q, capability=capability)
    except InvalidDirectoryFilterError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_directory_filter", "message": str(exc)},
        ) from exc
    return search_directory(session, filters=filters, limit=limit)
