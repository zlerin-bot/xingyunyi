from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response, status

from agentpost.access.schemas import (
    AccessPolicyResponse,
    AccessPolicyUpdate,
    AccessRuleCreate,
    AccessRuleResponse,
)
from agentpost.access.service import (
    AccessRuleAlreadyExistsError,
    AccessRuleNotFoundError,
    access_policy,
    create_access_rule,
    delete_access_rule,
    update_access_policy,
)
from agentpost.api.dependencies import CurrentAgentDep, SessionDep

router = APIRouter(prefix="/api/v1/agents", tags=["access-control"])


def _require_self(agent_id: UUID, current_agent: CurrentAgentDep) -> None:
    if current_agent.id != agent_id:
        # Do not disclose whether another agent or one of its rules exists.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "access_policy_not_found", "message": "Access policy was not found"},
        )


@router.get("/{agent_id}/access-policy", response_model=AccessPolicyResponse)
def read_access_policy(
    agent_id: UUID,
    session: SessionDep,
    current_agent: CurrentAgentDep,
) -> AccessPolicyResponse:
    _require_self(agent_id, current_agent)
    return access_policy(session, current_agent)


@router.put("/{agent_id}/access-policy", response_model=AccessPolicyResponse)
def replace_access_policy(
    request: Request,
    agent_id: UUID,
    payload: AccessPolicyUpdate,
    session: SessionDep,
    current_agent: CurrentAgentDep,
) -> AccessPolicyResponse:
    _require_self(agent_id, current_agent)
    return update_access_policy(
        session,
        owner_id=current_agent.id,
        inbound_policy=payload.inbound_policy,
        request_id=request.state.request_id,
    )


@router.post(
    "/{agent_id}/access-rules",
    response_model=AccessRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_access_rule(
    request: Request,
    agent_id: UUID,
    payload: AccessRuleCreate,
    session: SessionDep,
    current_agent: CurrentAgentDep,
) -> AccessRuleResponse:
    _require_self(agent_id, current_agent)
    try:
        return create_access_rule(
            session,
            owner_id=current_agent.id,
            payload=payload,
            request_id=request.state.request_id,
        )
    except AccessRuleAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "access_rule_already_exists",
                "message": "The canonical access rule already exists",
            },
        ) from exc


@router.delete(
    "/{agent_id}/access-rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_access_rule(
    request: Request,
    agent_id: UUID,
    rule_id: UUID,
    session: SessionDep,
    current_agent: CurrentAgentDep,
) -> Response:
    _require_self(agent_id, current_agent)
    try:
        delete_access_rule(
            session,
            owner_id=current_agent.id,
            rule_id=rule_id,
            request_id=request.state.request_id,
        )
    except AccessRuleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "access_rule_not_found", "message": "Access rule was not found"},
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
