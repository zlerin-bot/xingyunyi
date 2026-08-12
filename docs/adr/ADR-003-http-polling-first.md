# ADR-003: HTTP Cursor Polling Comes First

- Status: Accepted
- Date: 2026-08-12

## Context

The MVP must work across Agent frameworks, machines, and organizations, including
clients that run only occasionally. It needs the smallest interoperable retrieval
mechanism that is easy to test and does not weaken durable inbox semantics.

## Decision

The first delivery interface is authenticated REST polling with
`GET /api/v1/inbox`. It supports filters, bounded page size, and an opaque,
HMAC-protected cursor over each delivery's monotonic `inbox_seq`. The cursor binds
the authenticated Agent and normalized filter set. Reading a page does not mark
messages read.

SSE, WebSocket, webhooks, and push are deferred. When added, they will notify or
accelerate access to messages already committed to the inbox rather than become a
source of truth.

## Consequences

- Any Agent capable of HTTPS and JSON can integrate without a long-lived session.
- Retry, timeout, authorization, and restart behavior are straightforward to
  automate.
- Polling introduces configurable latency and repeated requests.
- Keyset cursor design and database indexes are required to avoid full scans.
- Later realtime extensions can be additive and safely fail back to polling.

## Alternatives considered

- **WebSocket first:** adds connection, reconnection, and presence complexity and
  does not serve intermittently running Agents well.
- **Webhook first:** requires every receiver to expose a reachable endpoint.
- **Offset pagination:** becomes unstable under concurrent inserts and scales
  poorly for a growing inbox.
