from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from agentpost.directory.schemas import DirectoryAgentProfile, DirectorySearchResponse
from agentpost.identity.models import Agent

MAX_QUERY_LENGTH = 200
MAX_CAPABILITY_LENGTH = 100


class InvalidDirectoryFilterError(ValueError):
    pass


def _normalize_text_query(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) > MAX_QUERY_LENGTH:
        raise InvalidDirectoryFilterError(
            f"q must contain at most {MAX_QUERY_LENGTH} characters"
        )
    normalized = value.strip().lower()
    if not normalized:
        raise InvalidDirectoryFilterError("q must not be blank")
    if any(ord(character) < 32 or ord(character) == 127 for character in normalized):
        raise InvalidDirectoryFilterError("q must not contain control characters")
    return normalized


def _normalize_capability(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) > MAX_CAPABILITY_LENGTH:
        raise InvalidDirectoryFilterError(
            f"capability must contain at most {MAX_CAPABILITY_LENGTH} characters"
        )
    normalized = value.strip().lower()
    if not normalized:
        raise InvalidDirectoryFilterError("capability must not be blank")
    if any(ord(character) < 32 or ord(character) == 127 for character in normalized):
        raise InvalidDirectoryFilterError("capability must not contain control characters")
    return normalized


@dataclass(frozen=True)
class DirectoryFilters:
    q: str | None
    capability: str | None

    @classmethod
    def normalize(
        cls,
        *,
        q: str | None,
        capability: str | None,
    ) -> DirectoryFilters:
        normalized_q = _normalize_text_query(q)
        normalized_capability = _normalize_capability(capability)
        if normalized_q is None and normalized_capability is None:
            raise InvalidDirectoryFilterError(
                "at least one of q or capability must be provided"
            )
        return cls(q=normalized_q, capability=normalized_capability)


def _directory_profile(agent: Agent) -> DirectoryAgentProfile:
    return DirectoryAgentProfile.model_validate(
        {
            **agent.public_attributes,
            "capability_verification": "self_declared",
        }
    )


def _has_capability(agent: Agent, capability: str) -> bool:
    # Registration canonicalizes capabilities, while normalization here also keeps
    # discovery correct for legacy rows created before that invariant existed.
    return any(
        isinstance(candidate, str) and candidate.strip().lower() == capability
        for candidate in (agent.capabilities or [])
    )


def search_directory(
    session: Session,
    *,
    filters: DirectoryFilters,
    limit: int = 20,
) -> DirectorySearchResponse:
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")

    query = select(Agent).where(Agent.status == "active")
    if filters.q is not None:
        # autoescape makes `%` and `_` literal substring characters rather than
        # allowing a search term to turn into an unrestricted LIKE expression.
        query = query.where(
            or_(
                func.lower(Agent.address).contains(filters.q, autoescape=True),
                func.lower(Agent.display_name).contains(filters.q, autoescape=True),
                func.lower(Agent.description).contains(filters.q, autoescape=True),
            )
        )

    query = query.order_by(Agent.address.asc())
    if filters.capability is None:
        agents = list(session.scalars(query.limit(limit)))
    else:
        # JSON membership operators differ between SQLite and PostgreSQL. Stream
        # ordered candidates and apply normalized exact membership in Python so
        # both development and production have identical behavior.
        agents = []
        for agent in session.scalars(query).yield_per(250):
            if _has_capability(agent, filters.capability):
                agents.append(agent)
                if len(agents) == limit:
                    break

    return DirectorySearchResponse(items=[_directory_profile(agent) for agent in agents])
