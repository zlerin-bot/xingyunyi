from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import desc, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agentpost.config import Settings
from agentpost.control.approval_schemas import (
    ApprovalDecisionCreate,
    ApprovalRequestCreate,
    ApprovalRequestResponse,
    OrbitApprovalRequest,
)
from agentpost.control.human_security import (
    add_human_action_audit,
    consume_human_confirmation,
)
from agentpost.control.models import (
    ApprovalDecision,
    ApprovalRequest,
    HumanUser,
)
from agentpost.control.service import AccessEntry, list_agent_access
from agentpost.identity.models import Agent, utc_now
from agentpost.messaging.models import AuditLog

_IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[\x21-\x7e]{1,255}$", flags=re.ASCII)
_DECISION_ROLES = frozenset({"owner", "operator"})


class ApprovalNotFoundError(Exception):
    pass


class ApprovalInvalidStateError(Exception):
    pass


class ApprovalIdempotencyConflictError(Exception):
    pass


class ApprovalInvalidIdempotencyKeyError(ValueError):
    pass


class ApprovalDecisionNotAllowedError(Exception):
    pass


@dataclass(frozen=True)
class ApprovalResult:
    approval: ApprovalRequest
    replayed: bool


@dataclass(frozen=True)
class ApprovalDecisionResult:
    approval: ApprovalRequest
    replayed: bool


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _validate_idempotency_key(value: str) -> str:
    if not _IDEMPOTENCY_KEY_PATTERN.fullmatch(value):
        raise ApprovalInvalidIdempotencyKeyError(
            "Idempotency-Key must contain 1-255 printable ASCII characters without spaces"
        )
    return value


def _canonical_hash(value: dict[str, object]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _approval_request_hash(payload: ApprovalRequestCreate) -> str:
    return _canonical_hash(
        {
            "operation": "create_approval_request",
            "payload": payload.model_dump(mode="json", exclude_none=False),
        }
    )


def _approval_decision_hash(
    approval_id: str,
    payload: ApprovalDecisionCreate,
) -> str:
    return _canonical_hash(
        {
            "operation": "decide_approval_request",
            "approval_id": approval_id,
            "payload": payload.model_dump(mode="json", exclude_none=False),
        }
    )


def effective_approval_status(approval: ApprovalRequest) -> str:
    if approval.status == "pending" and _as_utc(approval.expires_at) <= datetime.now(UTC):
        return "expired"
    return approval.status


def _decision_for(session: Session, approval: ApprovalRequest) -> ApprovalDecision | None:
    return session.scalar(
        select(ApprovalDecision).where(ApprovalDecision.approval_request_id == approval.id)
    )


def approval_response(
    session: Session,
    approval: ApprovalRequest,
) -> ApprovalRequestResponse:
    agent = session.get(Agent, approval.requested_by_agent_id)
    if agent is None:
        raise RuntimeError("approval request references a missing Agent")
    decision = _decision_for(session, approval)
    return ApprovalRequestResponse(
        approval_id=approval.approval_id,
        requester_agent_id=agent.id,
        requester_address=agent.address,
        action_type=approval.action_type,
        summary=approval.summary,
        justification=approval.justification,
        risk_level=approval.risk_level,
        payload=approval.request_payload,
        status=effective_approval_status(approval),
        expires_at=_as_utc(approval.expires_at),
        created_at=_as_utc(approval.created_at),
        updated_at=_as_utc(approval.updated_at),
        decided_at=_as_utc(approval.decided_at) if approval.decided_at else None,
        decision_note=decision.note if decision else None,
    )


def _load_agent_approval(
    session: Session,
    *,
    approval_id: str,
    agent_id: UUID,
    for_update: bool = False,
) -> ApprovalRequest:
    statement = select(ApprovalRequest).where(
        ApprovalRequest.approval_id == approval_id,
        ApprovalRequest.requested_by_agent_id == agent_id,
    )
    if for_update:
        statement = statement.with_for_update()
    approval = session.scalar(statement)
    if approval is None:
        raise ApprovalNotFoundError(approval_id)
    return approval


def create_approval_request(
    session: Session,
    settings: Settings,
    *,
    agent: Agent,
    payload: ApprovalRequestCreate,
    idempotency_key: str,
    request_id: str,
) -> ApprovalResult:
    key = _validate_idempotency_key(idempotency_key)
    request_hash = _approval_request_hash(payload)
    session.scalar(select(Agent).where(Agent.id == agent.id).with_for_update())
    existing = session.scalar(
        select(ApprovalRequest).where(
            ApprovalRequest.requested_by_agent_id == agent.id,
            ApprovalRequest.idempotency_key == key,
        )
    )
    if existing is not None:
        if existing.request_hash != request_hash:
            raise ApprovalIdempotencyConflictError(key)
        return ApprovalResult(approval=existing, replayed=True)

    now = utc_now()
    expires_at = payload.expires_at or (
        now + timedelta(seconds=settings.approval_default_ttl_seconds)
    )
    approval = ApprovalRequest(
        approval_id=f"apr_{uuid4().hex}",
        requested_by_agent_id=agent.id,
        action_type=payload.action_type,
        summary=payload.summary,
        justification=payload.justification,
        risk_level=payload.risk_level,
        request_payload=payload.payload,
        status="pending",
        idempotency_key=key,
        request_hash=request_hash,
        expires_at=expires_at,
        created_at=now,
        updated_at=now,
    )
    session.add(approval)
    try:
        session.flush()
        session.add(
            AuditLog(
                actor_agent_id=agent.id,
                action="approval.requested",
                target_type="approval_request",
                target_id=approval.approval_id,
                outcome="success",
                request_id=request_id,
                audit_metadata={
                    "action_type": approval.action_type,
                    "risk_level": approval.risk_level,
                    "expires_at": _as_utc(approval.expires_at).isoformat(),
                },
                created_at=now,
            )
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        existing = session.scalar(
            select(ApprovalRequest).where(
                ApprovalRequest.requested_by_agent_id == agent.id,
                ApprovalRequest.idempotency_key == key,
            )
        )
        if existing is None:
            raise
        if existing.request_hash != request_hash:
            raise ApprovalIdempotencyConflictError(key) from exc
        return ApprovalResult(approval=existing, replayed=True)
    return ApprovalResult(approval=approval, replayed=False)


def list_agent_approval_requests(
    session: Session,
    *,
    agent: Agent,
    limit: int,
    approval_status: str | None,
) -> list[ApprovalRequestResponse]:
    statement = select(ApprovalRequest).where(ApprovalRequest.requested_by_agent_id == agent.id)
    if approval_status == "pending":
        statement = statement.where(
            ApprovalRequest.status == "pending",
            ApprovalRequest.expires_at > datetime.now(UTC),
        )
    elif approval_status == "expired":
        statement = statement.where(
            or_(
                ApprovalRequest.status == "expired",
                (
                    (ApprovalRequest.status == "pending")
                    & (ApprovalRequest.expires_at <= datetime.now(UTC))
                ),
            )
        )
    elif approval_status:
        statement = statement.where(ApprovalRequest.status == approval_status)
    approvals = session.scalars(
        statement.order_by(desc(ApprovalRequest.created_at), desc(ApprovalRequest.id)).limit(limit)
    ).all()
    responses = [approval_response(session, approval) for approval in approvals]
    return responses


def get_agent_approval_request(
    session: Session,
    *,
    agent: Agent,
    approval_id: str,
) -> ApprovalRequestResponse:
    approval = _load_agent_approval(
        session,
        approval_id=approval_id,
        agent_id=agent.id,
    )
    return approval_response(session, approval)


def cancel_agent_approval_request(
    session: Session,
    *,
    agent: Agent,
    approval_id: str,
    request_id: str,
) -> ApprovalRequestResponse:
    approval = _load_agent_approval(
        session,
        approval_id=approval_id,
        agent_id=agent.id,
        for_update=True,
    )
    effective = effective_approval_status(approval)
    if effective == "expired":
        approval.status = "expired"
        approval.updated_at = utc_now()
        session.commit()
        return approval_response(session, approval)
    if approval.status == "cancelled":
        return approval_response(session, approval)
    if approval.status != "pending":
        raise ApprovalInvalidStateError(approval.status)
    now = utc_now()
    approval.status = "cancelled"
    approval.updated_at = now
    session.add(
        AuditLog(
            actor_agent_id=agent.id,
            action="approval.cancelled",
            target_type="approval_request",
            target_id=approval.approval_id,
            outcome="success",
            request_id=request_id,
            audit_metadata={},
            created_at=now,
        )
    )
    session.commit()
    return approval_response(session, approval)


def _human_access_entry(
    session: Session,
    *,
    user: HumanUser,
    agent_id: UUID,
) -> AccessEntry:
    entry = next(
        (
            candidate
            for candidate in list_agent_access(session, user)
            if candidate.agent.id == agent_id
        ),
        None,
    )
    if entry is None:
        raise ApprovalNotFoundError(str(agent_id))
    return entry


def _load_human_approval(
    session: Session,
    *,
    user: HumanUser,
    approval_id: str,
    for_update: bool = False,
) -> tuple[ApprovalRequest, AccessEntry]:
    statement = select(ApprovalRequest).where(ApprovalRequest.approval_id == approval_id)
    if for_update:
        statement = statement.with_for_update()
    approval = session.scalar(statement)
    if approval is None:
        raise ApprovalNotFoundError(approval_id)
    entry = _human_access_entry(
        session,
        user=user,
        agent_id=approval.requested_by_agent_id,
    )
    return approval, entry


def orbit_approval_response(
    session: Session,
    approval: ApprovalRequest,
    access: AccessEntry,
) -> OrbitApprovalRequest:
    redacted = access.role == "auditor"
    decision = _decision_for(session, approval)
    return OrbitApprovalRequest(
        approval_id=approval.approval_id,
        requester_agent_id=access.agent.id,
        requester_address=access.agent.address,
        action_type=approval.action_type,
        summary=None if redacted else approval.summary,
        justification=None if redacted else approval.justification,
        risk_level=approval.risk_level,
        payload={} if redacted else approval.request_payload,
        status=effective_approval_status(approval),
        access_role=access.role,
        can_decide=access.role in _DECISION_ROLES,
        content_redacted=redacted,
        expires_at=_as_utc(approval.expires_at),
        created_at=_as_utc(approval.created_at),
        updated_at=_as_utc(approval.updated_at),
        decided_at=_as_utc(approval.decided_at) if approval.decided_at else None,
        decision_note=None if redacted or decision is None else decision.note,
    )


def list_human_approval_requests(
    session: Session,
    *,
    user: HumanUser,
    limit: int,
    approval_status: str | None,
) -> list[OrbitApprovalRequest]:
    entries = list_agent_access(session, user)
    access_by_agent = {entry.agent.id: entry for entry in entries}
    if not access_by_agent:
        return []
    statement = select(ApprovalRequest).where(
        ApprovalRequest.requested_by_agent_id.in_(set(access_by_agent))
    )
    if approval_status == "pending":
        statement = statement.where(
            ApprovalRequest.status == "pending",
            ApprovalRequest.expires_at > datetime.now(UTC),
        )
    elif approval_status == "expired":
        statement = statement.where(
            or_(
                ApprovalRequest.status == "expired",
                (
                    (ApprovalRequest.status == "pending")
                    & (ApprovalRequest.expires_at <= datetime.now(UTC))
                ),
            )
        )
    elif approval_status:
        statement = statement.where(ApprovalRequest.status == approval_status)
    approvals = session.scalars(
        statement.order_by(desc(ApprovalRequest.created_at), desc(ApprovalRequest.id)).limit(limit)
    ).all()
    responses = [
        orbit_approval_response(
            session,
            approval,
            access_by_agent[approval.requested_by_agent_id],
        )
        for approval in approvals
    ]
    return responses


def pending_human_approval_count(
    session: Session,
    *,
    user: HumanUser,
) -> int:
    decision_agent_ids = {
        entry.agent.id
        for entry in list_agent_access(session, user)
        if entry.role in _DECISION_ROLES
    }
    if not decision_agent_ids:
        return 0
    value = session.scalar(
        select(func.count(ApprovalRequest.id)).where(
            ApprovalRequest.requested_by_agent_id.in_(decision_agent_ids),
            ApprovalRequest.status == "pending",
            ApprovalRequest.expires_at > datetime.now(UTC),
        )
    )
    return int(value or 0)


def get_human_approval_request(
    session: Session,
    *,
    user: HumanUser,
    approval_id: str,
) -> OrbitApprovalRequest:
    approval, access = _load_human_approval(
        session,
        user=user,
        approval_id=approval_id,
    )
    return orbit_approval_response(session, approval, access)


def authorize_human_approval_decision(
    session: Session,
    *,
    user: HumanUser,
    approval_id: str,
) -> ApprovalRequest:
    approval, access = _load_human_approval(
        session,
        user=user,
        approval_id=approval_id,
        for_update=True,
    )
    if access.role not in _DECISION_ROLES:
        raise ApprovalDecisionNotAllowedError(access.role)
    if effective_approval_status(approval) == "expired":
        approval.status = "expired"
        approval.updated_at = utc_now()
        session.commit()
        raise ApprovalInvalidStateError("expired")
    if approval.status != "pending":
        raise ApprovalInvalidStateError(approval.status)
    return approval


def decide_human_approval_request(
    session: Session,
    settings: Settings,
    *,
    user: HumanUser,
    human_session_id: UUID | None,
    approval_id: str,
    payload: ApprovalDecisionCreate,
    raw_confirmation: str,
    idempotency_key: str,
    request_id: str,
) -> ApprovalDecisionResult:
    key = _validate_idempotency_key(idempotency_key)
    request_hash = _approval_decision_hash(approval_id, payload)
    session.scalar(select(HumanUser).where(HumanUser.id == user.id).with_for_update())
    existing = session.scalar(
        select(ApprovalDecision).where(
            ApprovalDecision.human_user_id == user.id,
            ApprovalDecision.idempotency_key == key,
        )
    )
    if existing is not None:
        if existing.request_hash != request_hash:
            raise ApprovalIdempotencyConflictError(key)
        approval = session.get(ApprovalRequest, existing.approval_request_id)
        if approval is None:
            raise RuntimeError("approval decision references a missing request")
        return ApprovalDecisionResult(approval=approval, replayed=True)

    approval = authorize_human_approval_decision(
        session,
        user=user,
        approval_id=approval_id,
    )
    intent = "approve" if payload.decision == "approved" else "reject"
    confirmation = consume_human_confirmation(
        session,
        settings,
        user=user,
        human_session_id=human_session_id,
        intent=f"approval.{intent}",
        target_type="approval_request",
        target_id=approval.approval_id,
        raw_token=raw_confirmation,
    )
    now = utc_now()
    decision = ApprovalDecision(
        approval_request_id=approval.id,
        human_user_id=user.id,
        human_session_id=human_session_id,
        confirmation_id=confirmation.id,
        decision=payload.decision,
        note=payload.note,
        idempotency_key=key,
        request_hash=request_hash,
        created_at=now,
    )
    approval.status = payload.decision
    approval.updated_at = now
    approval.decided_at = now
    session.add(decision)
    add_human_action_audit(
        session,
        human_user_id=user.id,
        human_session_id=human_session_id,
        action="approval.decided",
        target_type="approval_request",
        target_id=approval.approval_id,
        outcome="success",
        request_id=request_id,
        audit_metadata={
            "decision": payload.decision,
            "execution_effect": "none",
        },
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        existing = session.scalar(
            select(ApprovalDecision).where(
                ApprovalDecision.human_user_id == user.id,
                ApprovalDecision.idempotency_key == key,
            )
        )
        if existing is not None:
            if existing.request_hash != request_hash:
                raise ApprovalIdempotencyConflictError(key) from exc
            replay = session.get(ApprovalRequest, existing.approval_request_id)
            if replay is None:
                raise RuntimeError("approval decision references a missing request") from exc
            return ApprovalDecisionResult(approval=replay, replayed=True)
        raise ApprovalInvalidStateError("already_decided") from exc
    return ApprovalDecisionResult(approval=approval, replayed=False)
