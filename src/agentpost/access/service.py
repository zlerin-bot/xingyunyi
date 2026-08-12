from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import exists, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agentpost.access.models import AccessRule
from agentpost.access.schemas import (
    AccessPolicyResponse,
    AccessRuleCreate,
    AccessRuleResponse,
    InboundPolicy,
)
from agentpost.identity.models import Agent, utc_now
from agentpost.messaging.models import AuditLog


class AccessRuleAlreadyExistsError(Exception):
    pass


class AccessRuleNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class DeliveryNotAllowedError(Exception):
    recipient_agent_id: UUID
    reason_code: str


def _lock_owner(session: Session, owner_id: UUID) -> Agent:
    owner = session.scalar(select(Agent).where(Agent.id == owner_id).with_for_update())
    if owner is None:  # Authenticated self-owned routes make this defensive only.
        raise AccessRuleNotFoundError(str(owner_id))
    return owner


def _rules_for_owner(session: Session, owner_id: UUID) -> list[AccessRule]:
    return list(
        session.scalars(
            select(AccessRule)
            .where(AccessRule.owner_agent_id == owner_id)
            .order_by(AccessRule.created_at.asc(), AccessRule.id.asc())
        )
    )


def _rule_response(rule: AccessRule) -> AccessRuleResponse:
    return AccessRuleResponse(
        id=rule.id,
        agent_id=rule.owner_agent_id,
        effect=rule.effect,
        subject_type=rule.subject_type,
        subject=rule.subject,
        created_at=rule.created_at,
    )


def access_policy(session: Session, owner: Agent) -> AccessPolicyResponse:
    return AccessPolicyResponse(
        agent_id=owner.id,
        inbound_policy=owner.inbound_policy,
        rules=[_rule_response(rule) for rule in _rules_for_owner(session, owner.id)],
    )


def update_access_policy(
    session: Session,
    *,
    owner_id: UUID,
    inbound_policy: InboundPolicy,
    request_id: str,
) -> AccessPolicyResponse:
    owner = _lock_owner(session, owner_id)
    previous = owner.inbound_policy
    owner.inbound_policy = inbound_policy
    session.add(
        AuditLog(
            actor_agent_id=owner.id,
            action="access.policy_updated",
            target_type="agent",
            target_id=str(owner.id),
            outcome="success",
            request_id=request_id,
            audit_metadata={"from": previous, "to": inbound_policy},
            created_at=utc_now(),
        )
    )
    session.commit()
    session.refresh(owner)
    return access_policy(session, owner)


def create_access_rule(
    session: Session,
    *,
    owner_id: UUID,
    payload: AccessRuleCreate,
    request_id: str,
) -> AccessRuleResponse:
    owner = _lock_owner(session, owner_id)
    rule = AccessRule(
        owner_agent_id=owner.id,
        effect=payload.effect,
        subject_type=payload.subject_type,
        subject=payload.subject,
        created_at=utc_now(),
    )
    session.add(rule)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise AccessRuleAlreadyExistsError(payload.subject) from exc
    session.add(
        AuditLog(
            actor_agent_id=owner.id,
            action="access.rule_created",
            target_type="access_rule",
            target_id=str(rule.id),
            outcome="success",
            request_id=request_id,
            audit_metadata={
                "effect": rule.effect,
                "subject_type": rule.subject_type,
                "subject": rule.subject,
            },
            created_at=utc_now(),
        )
    )
    session.commit()
    return _rule_response(rule)


def delete_access_rule(
    session: Session,
    *,
    owner_id: UUID,
    rule_id: UUID,
    request_id: str,
) -> None:
    owner = _lock_owner(session, owner_id)
    rule = session.scalar(
        select(AccessRule).where(
            AccessRule.id == rule_id,
            AccessRule.owner_agent_id == owner.id,
        )
    )
    if rule is None:
        session.rollback()
        raise AccessRuleNotFoundError(str(rule_id))
    audit = AuditLog(
        actor_agent_id=owner.id,
        action="access.rule_deleted",
        target_type="access_rule",
        target_id=str(rule.id),
        outcome="success",
        request_id=request_id,
        audit_metadata={
            "effect": rule.effect,
            "subject_type": rule.subject_type,
            "subject": rule.subject,
        },
        created_at=utc_now(),
    )
    session.delete(rule)
    session.add(audit)
    session.commit()


def lock_recipient_for_delivery(
    session: Session,
    *,
    sender: Agent,
    recipient_id: UUID | None = None,
    recipient_address: str | None = None,
) -> Agent:
    if (recipient_id is None) == (recipient_address is None):
        raise ValueError("exactly one recipient locator is required")
    locator = (
        Agent.id == recipient_id if recipient_id is not None else Agent.address == recipient_address
    )
    recipient = session.scalar(select(Agent).where(locator).with_for_update())
    if recipient is None or recipient.status != "active":
        # The messaging layer translates this to its non-enumerating not-found error.
        raise LookupError(recipient_address or recipient_id)

    rules = _rules_for_owner(session, recipient.id)
    matching = [
        rule
        for rule in rules
        if (rule.subject_type == "agent" and rule.subject == sender.address)
        or (rule.subject_type == "domain" and rule.subject == sender.domain)
    ]
    if any(rule.effect == "block" for rule in matching):
        raise DeliveryNotAllowedError(recipient.id, "explicit_block")
    if recipient.inbound_policy == "public":
        return recipient
    if recipient.inbound_policy == "private":
        if sender.id == recipient.id:
            return recipient
        raise DeliveryNotAllowedError(recipient.id, "private_policy")
    if any(rule.effect == "allow" for rule in matching):
        return recipient
    if recipient.inbound_policy == "contacts_only" and _has_existing_correspondence(
        session,
        first_agent_id=sender.id,
        second_agent_id=recipient.id,
    ):
        return recipient
    raise DeliveryNotAllowedError(recipient.id, "allow_rule_required")


def _has_existing_correspondence(
    session: Session,
    *,
    first_agent_id: UUID,
    second_agent_id: UUID,
) -> bool:
    # Import here to keep the access model independent from messaging model
    # import order while still implementing the MVP contact definition.
    from agentpost.messaging.models import Delivery, Message

    query = select(
        exists().where(
            Delivery.message_id == Message.id,
            or_(
                (
                    (Message.sender_agent_id == first_agent_id)
                    & (Delivery.recipient_agent_id == second_agent_id)
                ),
                (
                    (Message.sender_agent_id == second_agent_id)
                    & (Delivery.recipient_agent_id == first_agent_id)
                ),
            ),
        )
    )
    return bool(session.scalar(query))


def record_delivery_denied(
    session: Session,
    *,
    sender: Agent,
    error: DeliveryNotAllowedError,
    request_id: str,
) -> None:
    # A denial must never retain a partially built message, delivery, attachment
    # binding, or idempotency record.  The denial audit is its own transaction.
    session.rollback()
    session.add(
        AuditLog(
            actor_agent_id=sender.id,
            action="message.rejected",
            target_type="agent",
            target_id=str(error.recipient_agent_id),
            outcome="denied",
            reason_code=error.reason_code,
            request_id=request_id,
            audit_metadata={"recipient_agent_id": str(error.recipient_agent_id)},
            created_at=utc_now(),
        )
    )
    session.commit()
