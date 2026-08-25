from __future__ import annotations

import hmac
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status

from agentpost.api.dependencies import CurrentAgentDep, SessionDep, SettingsDep
from agentpost.identity.addressing import canonicalize_agent_address
from agentpost.identity.schemas import (
    AgentCreate,
    AgentProfile,
    AgentRegistrationResponse,
    AgentUpdate,
)
from agentpost.identity.service import (
    AddressAlreadyRegisteredError,
    HandleAlreadyRegisteredError,
    agent_profile,
    get_agent_by_address,
    get_agent_by_id,
    register_agent,
    update_agent,
)

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


def _handle_conflict(exc: HandleAlreadyRegisteredError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "handle_already_registered",
            "message": "This short Agent name is already in use",
            "details": {
                "handle": exc.handle,
                "suggestions": exc.suggestions,
            },
        },
    )


def _verify_registration_token(settings: SettingsDep, supplied_token: str | None) -> None:
    configured = settings.registration_token
    if configured is None:
        return
    expected = configured.get_secret_value().encode("utf-8")
    candidate = (supplied_token or "").encode("utf-8")
    if not hmac.compare_digest(candidate, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "registration_forbidden",
                "message": "A valid registration token is required",
            },
        )


@router.post("", response_model=AgentRegistrationResponse, status_code=status.HTTP_201_CREATED)
def create_agent(
    payload: AgentCreate,
    session: SessionDep,
    settings: SettingsDep,
    registration_token: Annotated[str | None, Header(alias="X-Registration-Token")] = None,
) -> AgentRegistrationResponse:
    _verify_registration_token(settings, registration_token)
    try:
        registered = register_agent(session, settings, payload)
    except AddressAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "address_already_registered",
                "message": "The canonical agent address is already registered",
            },
        ) from exc
    except HandleAlreadyRegisteredError as exc:
        raise _handle_conflict(exc) from exc
    return AgentRegistrationResponse(
        agent=agent_profile(registered.agent),
        api_key=registered.api_key,
        api_key_prefix=registered.api_key_prefix,
    )


@router.get("/by-address/{address}", response_model=AgentProfile)
def read_agent_by_address(address: str, session: SessionDep) -> AgentProfile:
    try:
        canonical_address = canonicalize_agent_address(address)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_agent_address", "message": str(exc)},
        ) from exc
    agent = get_agent_by_address(session, canonical_address)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "agent_not_found", "message": "Agent was not found"},
        )
    return agent_profile(agent)


@router.get("/{agent_id}", response_model=AgentProfile)
def read_agent(agent_id: UUID, session: SessionDep) -> AgentProfile:
    agent = get_agent_by_id(session, agent_id)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "agent_not_found", "message": "Agent was not found"},
        )
    return agent_profile(agent)


@router.patch("/{agent_id}", response_model=AgentProfile)
def patch_agent(
    agent_id: UUID,
    payload: AgentUpdate,
    session: SessionDep,
    current_agent: CurrentAgentDep,
) -> AgentProfile:
    if current_agent.id != agent_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "agent_access_denied",
                "message": "An agent may only update its own profile",
            },
        )
    try:
        updated = update_agent(session, current_agent, payload)
    except HandleAlreadyRegisteredError as exc:
        raise _handle_conflict(exc) from exc
    return agent_profile(updated)
