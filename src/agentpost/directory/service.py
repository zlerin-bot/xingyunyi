from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from agentpost.access.models import AccessRule
from agentpost.control.models import (
    AgentOwnership,
    HumanUser,
    Organization,
    OrganizationAgent,
    OrganizationMembership,
)
from agentpost.directory.schemas import (
    DirectoryAgentProfile,
    DirectorySearchResponse,
    RecipientCandidate,
    RecipientResolution,
)
from agentpost.identity.addressing import canonicalize_agent_address
from agentpost.identity.handles import HANDLE_PATTERN
from agentpost.identity.models import Agent
from agentpost.messaging.models import Delivery, Message
from agentpost.onboarding.models import (
    AgentConnectorBinding,
    ConnectorInstance,
)

MAX_QUERY_LENGTH = 200
MAX_CAPABILITY_LENGTH = 100


class InvalidDirectoryFilterError(ValueError):
    pass


_ADDRESS_TOKEN = re.compile(
    r"(?<![A-Za-z0-9._+-])([A-Za-z0-9][A-Za-z0-9._+-]*@[A-Za-z0-9][A-Za-z0-9.-]*)",
    flags=re.ASCII,
)
_HANDLE_TOKEN = re.compile(r"(?<![A-Za-z0-9-])([A-Za-z][A-Za-z0-9-]{2,31})(?![A-Za-z0-9-])")
_HUMAN_USERNAME_TOKEN = re.compile(
    r"(?<![A-Za-z0-9-])([A-Za-z0-9](?:[A-Za-z0-9-]{1,30}[A-Za-z0-9]))(?![A-Za-z0-9-])"
)
_GENERIC_AGENT_TERMS = frozenset({"agent", "智能体", "助手"})
_TYPE_LABELS = {
    "codex": "Codex",
    "workbuddy": "WorkBuddy",
    "doubao_work": "豆包工作",
    "openclaw": "OpenClaw",
    "hermes": "Hermes",
    "manus": "Manus",
}
_KNOWN_AGENT_TYPE_TERMS = frozenset(
    {
        *(_type.casefold() for _type in _TYPE_LABELS),
        *(label.casefold() for label in _TYPE_LABELS.values()),
    }
)
_TOKEN_AGENT_KIND_TERMS = frozenset(
    term
    for term in (_GENERIC_AGENT_TERMS | _KNOWN_AGENT_TYPE_TERMS)
    if HANDLE_PATTERN.fullmatch(term)
)
_INLINE_AGENT_KIND_TERMS = (
    _GENERIC_AGENT_TERMS | _KNOWN_AGENT_TYPE_TERMS
) - _TOKEN_AGENT_KIND_TERMS


@dataclass(frozen=True)
class _CandidateContext:
    agent: Agent
    owner_id: UUID | None = None
    owner_display_name: str | None = None
    owner_username: str | None = None
    agent_type: str | None = None
    organization_name: str | None = None


def _normalize_text_query(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) > MAX_QUERY_LENGTH:
        raise InvalidDirectoryFilterError(f"q must contain at most {MAX_QUERY_LENGTH} characters")
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
            raise InvalidDirectoryFilterError("at least one of q or capability must be provided")
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
    caller: Agent,
    filters: DirectoryFilters,
    limit: int = 20,
) -> DirectorySearchResponse:
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")

    related_agent_ids = _related_agent_ids(session, caller)
    query = select(Agent).where(
        Agent.status == "active",
        Agent.id.in_(related_agent_ids),
    )
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


def _related_agent_ids(session: Session, caller: Agent) -> set[UUID]:
    """Return the server-verified contact/organization discovery scope."""

    related = {caller.id}
    contact_source_ids = {caller.id}
    caller_owner_id = session.scalar(
        select(AgentOwnership.human_user_id).where(AgentOwnership.agent_id == caller.id)
    )
    if caller_owner_id is not None:
        owned_agent_ids = set(
            session.scalars(
                select(AgentOwnership.agent_id).where(
                    AgentOwnership.human_user_id == caller_owner_id
                )
            )
        )
        related.update(owned_agent_ids)
        # A Human's newly connected Agent must be able to address contacts that
        # another Agent owned by the same Human has already corresponded with.
        # This shares only the server-verified contact edge, never message bodies.
        contact_source_ids.update(owned_agent_ids)
        organization_ids = list(
            session.scalars(
                select(OrganizationMembership.organization_id).where(
                    OrganizationMembership.human_user_id == caller_owner_id
                )
            )
        )
        if organization_ids:
            related.update(
                session.scalars(
                    select(OrganizationAgent.agent_id).where(
                        OrganizationAgent.organization_id.in_(organization_ids)
                    )
                )
            )

    related.update(
        session.scalars(
            select(Delivery.recipient_agent_id)
            .join(Message, Message.id == Delivery.message_id)
            .where(Message.sender_agent_id.in_(contact_source_ids))
        )
    )
    related.update(
        session.scalars(
            select(Message.sender_agent_id)
            .join(Delivery, Delivery.message_id == Message.id)
            .where(Delivery.recipient_agent_id.in_(contact_source_ids))
        )
    )
    related.update(
        session.scalars(
            select(AccessRule.owner_agent_id).where(
                AccessRule.effect == "allow",
                or_(
                    (AccessRule.subject_type == "agent") & (AccessRule.subject == caller.address),
                    (AccessRule.subject_type == "domain") & (AccessRule.subject == caller.domain),
                ),
            )
        )
    )
    return related


def _candidate_contexts(session: Session, caller: Agent) -> list[_CandidateContext]:
    related_ids = _related_agent_ids(session, caller)
    rows = session.execute(
        select(
            Agent,
            HumanUser.id,
            HumanUser.display_name,
            HumanUser.username,
            ConnectorInstance.connector_type,
            Organization.name,
        )
        .outerjoin(AgentOwnership, AgentOwnership.agent_id == Agent.id)
        .outerjoin(HumanUser, HumanUser.id == AgentOwnership.human_user_id)
        .outerjoin(AgentConnectorBinding, AgentConnectorBinding.agent_id == Agent.id)
        .outerjoin(
            ConnectorInstance,
            ConnectorInstance.id == AgentConnectorBinding.connector_instance_id,
        )
        .outerjoin(OrganizationAgent, OrganizationAgent.agent_id == Agent.id)
        .outerjoin(Organization, Organization.id == OrganizationAgent.organization_id)
        .where(Agent.id.in_(related_ids), Agent.status == "active")
        .order_by(Agent.address)
    ).all()
    return [
        _CandidateContext(
            agent=agent,
            owner_id=owner_id,
            owner_display_name=owner_name,
            owner_username=owner_username,
            agent_type=agent_type,
            organization_name=organization_name,
        )
        for agent, owner_id, owner_name, owner_username, agent_type, organization_name in rows
    ]


def _owned_human_contexts(session: Session, human: HumanUser) -> list[_CandidateContext]:
    rows = session.execute(
        select(Agent, ConnectorInstance.connector_type)
        .join(AgentOwnership, AgentOwnership.agent_id == Agent.id)
        .outerjoin(AgentConnectorBinding, AgentConnectorBinding.agent_id == Agent.id)
        .outerjoin(
            ConnectorInstance,
            ConnectorInstance.id == AgentConnectorBinding.connector_instance_id,
        )
        .where(
            AgentOwnership.human_user_id == human.id,
            Agent.status == "active",
        )
        .order_by(Agent.address)
    ).all()
    return [
        _CandidateContext(
            agent=agent,
            owner_id=human.id,
            owner_display_name=human.display_name,
            owner_username=human.username,
            agent_type=agent_type,
        )
        for agent, agent_type in rows
    ]


def _default_human_context(
    session: Session,
    human: HumanUser,
) -> _CandidateContext | None:
    if human.default_agent_id is None:
        return None
    return next(
        (
            context
            for context in _owned_human_contexts(session, human)
            if context.agent.id == human.default_agent_id
        ),
        None,
    )


def _contexts_for_targeted_human(
    session: Session,
    *,
    human: HumanUser,
    normalized_query: str,
) -> list[_CandidateContext]:
    contexts = _owned_human_contexts(session, human)
    return _select_targeted_contexts(
        contexts,
        default_agent_id=human.default_agent_id,
        normalized_query=normalized_query,
    )


def _select_targeted_contexts(
    contexts: list[_CandidateContext],
    *,
    default_agent_id: UUID | None,
    normalized_query: str,
) -> list[_CandidateContext]:
    typed = [
        context
        for context in contexts
        if _query_mentions_agent_type(normalized_query, context.agent_type)
    ]
    if typed:
        return typed
    handles = set(_handle_tokens(normalized_query))
    named = [
        context
        for context in contexts
        if (context.agent.handle and context.agent.handle in handles)
        or context.agent.display_name.strip().casefold() in normalized_query
    ]
    if named:
        return named
    default = next(
        (context for context in contexts if context.agent.id == default_agent_id),
        None,
    )
    return [default] if default is not None else []


def _human_username_tokens(query: str) -> list[str]:
    tokens: list[str] = []
    normalized = query.strip().casefold()
    for token in [
        normalized,
        *(match.group(1).casefold() for match in _HUMAN_USERNAME_TOKEN.finditer(query)),
    ]:
        if token not in tokens:
            tokens.append(token)
    return tokens


def _fuzzy_human_contexts(session: Session, query: str) -> list[_CandidateContext]:
    fuzzy_terms = [
        token
        for token in _human_username_tokens(query)
        if token not in _GENERIC_AGENT_TERMS and token not in _KNOWN_AGENT_TYPE_TERMS
    ]
    matches: list[tuple[float, HumanUser]] = []
    for human in session.scalars(
        select(HumanUser)
        .where(HumanUser.status == "active", HumanUser.default_agent_id.is_not(None))
        .order_by(HumanUser.username)
    ):
        score = 0.0
        for term in fuzzy_terms:
            if len(term) < 2:
                continue
            for value in (human.username, human.display_name):
                normalized_value = value.strip().casefold()
                if term in normalized_value or normalized_value in term:
                    score = max(score, 0.9)
                elif len(term) >= 4:
                    score = max(score, SequenceMatcher(None, term, normalized_value).ratio())
        if score >= 0.72:
            matches.append((score, human))
    matches.sort(key=lambda item: (-item[0], item[1].username))
    return [
        context
        for _, human in matches
        if (context := _default_human_context(session, human)) is not None
    ]


def _address_from_query(query: str) -> str | None:
    tokens = [query, *(match.group(1) for match in _ADDRESS_TOKEN.finditer(query))]
    for token in tokens:
        try:
            return canonicalize_agent_address(token.strip("，。！？；：,.!?;:()[]{}<>\"'"))
        except ValueError:
            continue
    return None


def _handle_tokens(query: str) -> list[str]:
    tokens: list[str] = []
    exact = query.strip().lower()
    if HANDLE_PATTERN.fullmatch(exact):
        tokens.append(exact)
    for match in _HANDLE_TOKEN.finditer(query):
        token = match.group(1).lower()
        if HANDLE_PATTERN.fullmatch(token) and token not in tokens:
            tokens.append(token)
    return tokens


def _type_label(agent_type: str | None) -> str | None:
    if agent_type is None:
        return None
    return _TYPE_LABELS.get(agent_type.casefold(), agent_type)


def _query_mentions_agent_type(query: str, agent_type: str | None) -> bool:
    if agent_type is None:
        return False
    normalized_type = agent_type.casefold()
    label = _TYPE_LABELS.get(normalized_type)
    terms = {normalized_type}
    if label is not None:
        terms.add(label.casefold())
    tokens = set(_handle_tokens(query))
    return any(
        term in tokens if HANDLE_PATTERN.fullmatch(term) else term in query for term in terms
    )


def _looks_like_human_agent_query(query: str) -> bool:
    """Detect an explicit owner constraint so resolution can fail closed.

    A phrase such as ``020 的 Codex`` must not fall back to a globally unique
    ``codex`` handle when 020 is outside the caller's relationship scope.
    """

    normalized = query.casefold()
    suffixes: list[str] = []
    if "的" in normalized:
        suffixes.append(normalized.rsplit("的", maxsplit=1)[1])
    for possessive in ("'s", "’s"):
        if possessive in normalized:
            suffixes.append(normalized.rsplit(possessive, maxsplit=1)[1])
    for suffix in suffixes:
        stripped = suffix.lstrip(" \t:：([{（【<《\"'")
        if any(stripped.startswith(term) for term in _INLINE_AGENT_KIND_TERMS):
            return True
        first_token = _HANDLE_TOKEN.search(stripped)
        if (
            first_token is not None
            and first_token.start() == 0
            and first_token.group(1).casefold() in _TOKEN_AGENT_KIND_TERMS
        ):
            return True
    return False


def _friendly_candidates(
    contexts: list[_CandidateContext],
    *,
    match_kind: str,
) -> list[RecipientCandidate]:
    owner_name_counts: dict[str, set[UUID | None]] = {}
    owner_type_counts: dict[tuple[UUID | None, str], int] = {}
    for context in contexts:
        if context.owner_display_name:
            owner_name_counts.setdefault(context.owner_display_name.casefold(), set()).add(
                context.owner_id
            )
        part = _type_label(context.agent_type) or context.agent.display_name
        owner_type_counts[(context.owner_id, part.casefold())] = (
            owner_type_counts.get((context.owner_id, part.casefold()), 0) + 1
        )

    candidates: list[RecipientCandidate] = []
    for context in contexts:
        agent_part = _type_label(context.agent_type) or context.agent.display_name
        if context.owner_display_name:
            owner_part = context.owner_display_name
            if (
                len(owner_name_counts[context.owner_display_name.casefold()]) > 1
                and context.organization_name
            ):
                owner_part = f"{owner_part}（{context.organization_name}）"
            label = f"{owner_part}的 {agent_part}"
        elif context.agent.handle:
            label = context.agent.handle
        else:
            label = context.agent.display_name

        if owner_type_counts.get((context.owner_id, agent_part.casefold()), 0) > 1:
            qualifier = context.agent.handle or context.agent.display_name
            if qualifier.casefold() != agent_part.casefold():
                label = f"{label}（{qualifier}）"

        candidates.append(
            RecipientCandidate(
                agent_id=context.agent.id,
                address=context.agent.address,
                handle=context.agent.handle,
                display_name=context.agent.display_name,
                owner_display_name=context.owner_display_name,
                owner_username=context.owner_username,
                agent_type=context.agent_type,
                organization_name=context.organization_name,
                label=label,
                match_kind=match_kind,
            )
        )
    return candidates


def _resolution(
    query: str,
    contexts: list[_CandidateContext],
    match_kind: str,
) -> RecipientResolution:
    candidates = _friendly_candidates(contexts, match_kind=match_kind)
    if len(candidates) == 1:
        return RecipientResolution(
            status="resolved",
            query=query,
            match=candidates[0],
            total_candidates=1,
            reason="unique_match",
        )
    if candidates:
        return RecipientResolution(
            status="needs_clarification",
            query=query,
            candidates=candidates[:5],
            total_candidates=len(candidates),
            reason="recipient_ambiguous",
        )
    return RecipientResolution(
        status="not_found",
        query=query,
        reason="recipient_not_found",
    )


def _clarification_resolution(
    query: str,
    contexts: list[_CandidateContext],
    match_kind: str,
) -> RecipientResolution:
    candidates = _friendly_candidates(contexts, match_kind=match_kind)
    if candidates:
        return RecipientResolution(
            status="needs_clarification",
            query=query,
            candidates=candidates[:5],
            total_candidates=len(candidates),
            reason="recipient_ambiguous",
        )
    return RecipientResolution(
        status="not_found",
        query=query,
        reason="recipient_not_found",
    )


def _context_for_exact_agent(
    agent: Agent,
    scoped_by_id: dict[UUID, _CandidateContext],
) -> _CandidateContext:
    # Owner and organization metadata is disclosed only when the target is already
    # inside the caller's relationship scope.
    return scoped_by_id.get(agent.id, _CandidateContext(agent=agent))


def resolve_recipient(session: Session, *, caller: Agent, query: str) -> RecipientResolution:
    """Resolve natural recipient text without ever synthesizing an Agent address."""

    cleaned_query = query.strip()
    normalized_query = cleaned_query.casefold()
    scoped = _candidate_contexts(session, caller)
    scoped_by_id = {context.agent.id: context for context in scoped}

    address = _address_from_query(cleaned_query)
    if address is not None:
        exact = session.scalar(
            select(Agent).where(Agent.address == address, Agent.status == "active")
        )
        contexts = [_context_for_exact_agent(exact, scoped_by_id)] if exact is not None else []
        return _resolution(cleaned_query, contexts, "address")

    username_tokens = [
        token
        for token in _human_username_tokens(cleaned_query)
        if token not in _GENERIC_AGENT_TERMS and token not in _KNOWN_AGENT_TYPE_TERMS
    ]
    exact_humans = list(
        session.scalars(
            select(HumanUser)
            .where(
                HumanUser.username.in_(username_tokens),
                HumanUser.status == "active",
            )
            .order_by(HumanUser.username)
        )
    )
    if exact_humans:
        contexts = [
            context
            for human in exact_humans
            for context in _contexts_for_targeted_human(
                session,
                human=human,
                normalized_query=normalized_query,
            )
        ]
        return _resolution(cleaned_query, contexts, "human_agent")

    scoped_display_humans = [
        context
        for context in scoped
        if context.owner_display_name
        and len(context.owner_display_name.strip()) >= 2
        and context.owner_display_name.strip().casefold() in normalized_query
    ]
    if scoped_display_humans:
        contexts: list[_CandidateContext] = []
        owner_ids = list(
            dict.fromkeys(context.owner_id for context in scoped_display_humans if context.owner_id)
        )
        humans = {
            human.id: human
            for human in session.scalars(select(HumanUser).where(HumanUser.id.in_(owner_ids)))
        }
        for owner_id in owner_ids:
            owner_contexts = [
                context for context in scoped_display_humans if context.owner_id == owner_id
            ]
            contexts.extend(
                _select_targeted_contexts(
                    owner_contexts,
                    default_agent_id=humans[owner_id].default_agent_id,
                    normalized_query=normalized_query,
                )
            )
        return _resolution(cleaned_query, contexts, "human_agent")

    exact_display_humans = [
        human
        for human in session.scalars(
            select(HumanUser)
            .where(HumanUser.status == "active", HumanUser.default_agent_id.is_not(None))
            .order_by(HumanUser.display_name, HumanUser.username)
        )
        if len(human.display_name.strip()) >= 2
        and human.display_name.strip().casefold() in normalized_query
    ]
    if exact_display_humans:
        contexts = [
            context
            for human in exact_display_humans
            for context in _contexts_for_targeted_human(
                session,
                human=human,
                normalized_query=normalized_query,
            )
        ]
        return _resolution(cleaned_query, contexts, "human_agent")

    if HANDLE_PATTERN.fullmatch(normalized_query):
        exact_handle = session.scalar(
            select(Agent).where(Agent.handle == normalized_query, Agent.status == "active")
        )
        if exact_handle is not None:
            return _resolution(
                cleaned_query,
                [_context_for_exact_agent(exact_handle, scoped_by_id)],
                "handle",
            )

    display_matches = [
        context
        for context in scoped
        if context.agent.display_name.strip().casefold() == normalized_query
    ]
    if display_matches:
        return _resolution(cleaned_query, display_matches, "display_name")

    username_matches = [
        context
        for context in scoped
        if context.owner_username
        and re.search(
            rf"(?<![a-z0-9-]){re.escape(context.owner_username.casefold())}(?![a-z0-9-])",
            normalized_query,
        )
    ]
    owner_matches = username_matches or [
        context
        for context in scoped
        if context.owner_display_name
        and context.owner_display_name.strip().casefold() in normalized_query
    ]
    if owner_matches:
        handles = [
            token
            for token in _handle_tokens(cleaned_query)
            if token not in _GENERIC_AGENT_TERMS and token not in _KNOWN_AGENT_TYPE_TERMS
        ]
        handled = [
            context
            for context in owner_matches
            if context.agent.handle and context.agent.handle in handles
        ]
        if handled:
            owner_matches = handled
        else:
            typed = [
                context
                for context in owner_matches
                if _query_mentions_agent_type(normalized_query, context.agent_type)
            ]
            if typed:
                owner_matches = typed
            else:
                named = [
                    context
                    for context in owner_matches
                    if context.agent.display_name.strip().casefold() in normalized_query
                ]
                if named:
                    owner_matches = named
        return _resolution(cleaned_query, owner_matches, "human_agent")

    if _looks_like_human_agent_query(cleaned_query):
        human_contexts = _fuzzy_human_contexts(session, cleaned_query)
        if human_contexts:
            return _clarification_resolution(cleaned_query, human_contexts, "fuzzy")
        return _resolution(cleaned_query, [], "human_agent")

    handles = _handle_tokens(cleaned_query)
    if handles:
        handle_agents = list(
            session.scalars(
                select(Agent)
                .where(Agent.handle.in_(handles), Agent.status == "active")
                .order_by(Agent.handle)
            )
        )
        if handle_agents:
            return _resolution(
                cleaned_query,
                [_context_for_exact_agent(agent, scoped_by_id) for agent in handle_agents],
                "handle",
            )

    human_contexts = _fuzzy_human_contexts(session, cleaned_query)
    if human_contexts:
        return _clarification_resolution(cleaned_query, human_contexts, "fuzzy")

    fuzzy_matches: list[tuple[float, _CandidateContext]] = []
    for context in scoped:
        values = [
            context.agent.handle,
            context.agent.display_name,
            context.owner_display_name,
            context.owner_username,
            context.agent_type,
            context.organization_name,
        ]
        score = 0.0
        for value in values:
            if not value:
                continue
            normalized_value = value.strip().casefold()
            if normalized_value in _GENERIC_AGENT_TERMS:
                continue
            if normalized_value in normalized_query or normalized_query in normalized_value:
                score = max(score, 0.9)
            else:
                similarity = SequenceMatcher(None, normalized_query, normalized_value).ratio()
                score = max(score, similarity)
        if score >= 0.72:
            fuzzy_matches.append((score, context))
    fuzzy_matches.sort(key=lambda item: (-item[0], item[1].agent.address))
    return _resolution(
        cleaned_query,
        [context for _, context in fuzzy_matches],
        "fuzzy",
    )
