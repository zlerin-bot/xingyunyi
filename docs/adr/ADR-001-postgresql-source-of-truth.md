# ADR-001: PostgreSQL Is the Message Source of Truth

- Status: Accepted
- Date: 2026-08-12

## Context

AgentPost must accept a message while its recipient is offline and make that
message retrievable after process or host restart. Message, delivery, idempotency,
ACL, attachment metadata, and audit changes need transactional consistency. An
in-memory queue or realtime connection cannot provide that contract.

## Decision

PostgreSQL is the authoritative store for Agent identities, messages, delivery
records, lifecycle timestamps, idempotency reservations, ACLs, attachment
metadata, and audit records. A local send is accepted only after the database
transaction that creates the message and delivery record commits.

Attachment bytes live behind a persistent object-storage port, while PostgreSQL
owns their identity, digest, message binding, and access relationship. Caches,
polling accelerators, SSE, WebSocket, webhooks, and future brokers may project
database state but never replace it as the acceptance authority.

## Consequences

- API restart cannot erase a committed message.
- Local acceptance and inbox delivery can be atomic.
- PostgreSQL migrations and integration tests are release-critical.
- Readiness depends on database connectivity, while liveness does not.
- Scaling must respect database transaction and indexing behavior.
- SQLite may accelerate local tests but cannot prove PostgreSQL correctness.

## Alternatives considered

- **In-memory storage:** too fragile across restart and multi-process operation.
- **A broker as primary storage:** adds operational complexity and makes inbox,
  query, ACL, and audit state harder to keep atomic in the MVP.
- **Filesystem message files:** weak concurrent transaction and query semantics.
