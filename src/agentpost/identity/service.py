from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agentpost.config import Settings
from agentpost.identity.addressing import address_domain, address_local_id
from agentpost.identity.api_keys import api_key_prefix, digest_api_key, generate_api_key
from agentpost.identity.models import Agent, AgentApiKey
from agentpost.identity.schemas import AgentCreate, AgentProfile, AgentUpdate


class AddressAlreadyRegisteredError(Exception):
    pass


@dataclass(frozen=True)
class RegisteredAgent:
    agent: Agent
    api_key: str
    api_key_prefix: str


def register_agent(session: Session, settings: Settings, payload: AgentCreate) -> RegisteredAgent:
    raw_api_key = generate_api_key()
    agent = Agent(
        address=payload.address,
        display_name=payload.display_name or address_local_id(payload.address),
        description=payload.description,
        domain=address_domain(payload.address),
        status="active",
        public_key=payload.public_key,
        capabilities=payload.capabilities,
        endpoint=payload.endpoint,
    )
    credential = AgentApiKey(
        agent=agent,
        key_digest=digest_api_key(raw_api_key, settings.api_key_pepper),
        key_prefix=api_key_prefix(raw_api_key),
    )
    session.add_all([agent, credential])
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise AddressAlreadyRegisteredError(payload.address) from exc
    session.refresh(agent)
    return RegisteredAgent(
        agent=agent,
        api_key=raw_api_key,
        api_key_prefix=credential.key_prefix,
    )


def get_agent_by_id(session: Session, agent_id: UUID) -> Agent | None:
    return session.get(Agent, agent_id)


def get_agent_by_address(session: Session, address: str) -> Agent | None:
    return session.scalar(select(Agent).where(Agent.address == address))


def update_agent(session: Session, agent: Agent, payload: AgentUpdate) -> Agent:
    updates = payload.model_dump(exclude_unset=True)
    for field_name, value in updates.items():
        setattr(agent, field_name, value)
    session.commit()
    session.refresh(agent)
    return agent


def agent_profile(agent: Agent) -> AgentProfile:
    return AgentProfile.model_validate(agent.public_attributes)
