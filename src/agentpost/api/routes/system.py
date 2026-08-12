from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from agentpost import __version__
from agentpost.api.dependencies import DatabaseDep

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: str
    version: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)


@router.get("/ready", response_model=HealthResponse)
def ready(database: DatabaseDep) -> HealthResponse:
    try:
        database.ping()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "database_unavailable", "message": "Database is not ready"},
        ) from exc
    return HealthResponse(status="ready", version=__version__)
