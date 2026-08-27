from __future__ import annotations

from fastapi import APIRouter, Response

from agentpost.api.dependencies import SettingsDep
from agentpost.protocol_contract import (
    PROTOCOL_CONTRACT_VERSION,
    AgentIntegrationContract,
    build_agent_integration_contract,
)

router = APIRouter(tags=["agent-integration-contract"])


@router.get("/api/v1/protocol/contract", response_model=AgentIntegrationContract)
def agent_integration_contract(
    response: Response,
    settings: SettingsDep,
) -> AgentIntegrationContract:
    response.headers["Cache-Control"] = "public, max-age=300"
    response.headers["X-AgentPost-Contract-Version"] = PROTOCOL_CONTRACT_VERSION
    response.headers["X-Content-Type-Options"] = "nosniff"
    return build_agent_integration_contract(settings)
