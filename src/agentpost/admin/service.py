from __future__ import annotations

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from agentpost.admin.schemas import (
    AdminAgent,
    AdminAudit,
    AdminDelivery,
    AdminMessage,
    AdminThread,
)
from agentpost.identity.models import Agent
from agentpost.messaging.models import AuditLog, Delivery, Message


def list_agents(session: Session, *, limit: int) -> list[AdminAgent]:
    agents = session.scalars(select(Agent).order_by(Agent.address).limit(limit)).all()
    return [
        AdminAgent(
            id=agent.id,
            address=agent.address,
            display_name=agent.display_name,
            domain=agent.domain,
            status=agent.status,
            inbound_policy=agent.inbound_policy,
            capabilities=list(agent.capabilities),
            created_at=agent.created_at,
            updated_at=agent.updated_at,
            last_seen_at=agent.last_seen_at,
        )
        for agent in agents
    ]


def list_messages(session: Session, *, limit: int) -> list[AdminMessage]:
    rows = session.execute(
        select(Message, Delivery)
        .join(Delivery, Delivery.message_id == Message.id)
        .order_by(desc(Message.created_at), desc(Message.id))
        .limit(limit)
    ).all()
    return [
        AdminMessage(
            message_id=message.id,
            sender_agent_id=message.sender_agent_id,
            recipient_agent_id=delivery.recipient_agent_id,
            message_type=message.message_type,
            subject=message.subject,
            thread_id=message.thread_id,
            reply_to=message.reply_to_message_id,
            priority=message.priority,
            created_at=message.created_at,
            accepted_at=message.accepted_at,
            delivery_status=delivery.delivery_status,
        )
        for message, delivery in rows
    ]


def list_threads(session: Session, *, limit: int) -> list[AdminThread]:
    rows = session.execute(
        select(
            Message.thread_id,
            func.count(Message.id),
            func.max(Message.created_at),
        )
        .group_by(Message.thread_id)
        .order_by(desc(func.max(Message.created_at)))
        .limit(limit)
    ).all()
    return [
        AdminThread(thread_id=thread_id, message_count=count, last_message_at=last_at)
        for thread_id, count, last_at in rows
    ]


def list_deliveries(session: Session, *, limit: int) -> list[AdminDelivery]:
    deliveries = session.scalars(
        select(Delivery).order_by(desc(Delivery.inbox_seq)).limit(limit)
    ).all()
    return [
        AdminDelivery(
            delivery_id=delivery.id,
            message_id=delivery.message_id,
            recipient_agent_id=delivery.recipient_agent_id,
            inbox_seq=delivery.inbox_seq,
            status=delivery.delivery_status,
            attempts=delivery.delivery_attempts,
            delivered_at=delivery.delivered_at,
            read_at=delivery.read_at,
            acked_at=delivery.acked_at,
            error=delivery.error,
        )
        for delivery in deliveries
    ]


def list_audit_logs(session: Session, *, limit: int) -> list[AdminAudit]:
    logs = session.scalars(
        select(AuditLog).order_by(desc(AuditLog.created_at), desc(AuditLog.id)).limit(limit)
    ).all()
    return [
        AdminAudit(
            id=entry.id,
            actor_agent_id=entry.actor_agent_id,
            action=entry.action,
            target_type=entry.target_type,
            target_id=entry.target_id,
            outcome=entry.outcome,
            reason_code=entry.reason_code,
            request_id=entry.request_id,
            metadata=entry.audit_metadata,
            created_at=entry.created_at,
        )
        for entry in logs
    ]
