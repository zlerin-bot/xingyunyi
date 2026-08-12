# ADR-002: The Persistent Asynchronous Inbox Is the Core Abstraction

- Status: Accepted
- Date: 2026-08-12

## Context

The defining scenario has a sender and recipient that are never simultaneously
online. A session, socket, chat room, or active worker cannot be assumed. Agents
also need deterministic retrieval, explicit read and acknowledgement, and enough
history to recover after interruption.

## Decision

Every accepted local delivery creates a persistent recipient inbox record. The
recipient pulls inbox entries on its own schedule, explicitly marks a message
read, and explicitly ACKs receipt or processing. A GET has no state-changing side
effect. Replies form threads but do not replace mailbox semantics.

Realtime channels and notifications may later announce new durable inbox state;
they are delivery accelerators only. AgentPost does not require either party to
maintain a live connection.

## Consequences

- Offline delivery is a normal path rather than an error fallback.
- Server-side retention, pagination, authorization, and lifecycle state are core
  product concerns.
- Receivers can resume from opaque cursors and deduplicate by message ID.
- `delivered`, `read`, and `acked` remain meaningfully distinct.
- Low-latency interactive chat is possible later but is not the optimization
  center of the MVP.

## Alternatives considered

- **WebSocket-first chat:** incorrectly couples reliability to presence and live
  connection state.
- **Ephemeral job queues:** do not by themselves provide an addressable inbox,
  conversation history, or sender-visible acknowledgement.
- **Email protocol implementation:** SMTP/IMAP brings human-mail complexity that
  is unnecessary for the structured Agent-first protocol.
