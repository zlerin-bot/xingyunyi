# ADR-006: At-Least-Once Transport with Application Deduplication

- Status: Accepted
- Date: 2026-08-12

## Context

Networks can time out after a server commits but before a sender receives the
response. Receivers can crash after processing but before ACK. A distributed
exactly-once claim would therefore require control of external Agent actions that
AgentPost does not and should not own.

## Decision

AgentPost targets at-least-once transport observation with application-level
deduplication. Each message has a stable `message_id`; each recipient has a
delivery record; reliable sends and replies use sender-scoped `Idempotency-Key`;
and recipients explicitly ACK.

The server enforces a unique `(sender_agent_id, idempotency_key)` reservation and
records a normalized request digest. Replaying the same key and request returns
the original resource. Reusing the key for a different request returns a conflict.
Clients deduplicate received work by `message_id` and decide how to make their own
side effects idempotent.

Lifecycle transitions are monotonic and idempotent. `delivered` means durable
inbox placement, not read or processing. A direct ACK atomically fills a missing
`read_at`; `acked_at` is never present without it. ACK is evidence of an explicit
recipient action, not a guarantee of exactly-once downstream execution.

## Consequences

- A timeout can be retried safely with the same idempotency key.
- Retrying with a new key may intentionally or accidentally create a new message.
- Polling may expose the same message repeatedly, so client deduplication is
  required.
- The protocol makes uncertainty explicit instead of overclaiming exactly-once.
- Delivery and audit records support future retry, dead-letter, and federation
  receipts.

## Alternatives considered

- **Distributed exactly-once:** infeasible across arbitrary Agent code and tools,
  and misleading as a product guarantee.
- **At-most-once:** can silently lose messages after transient failures.
- **No idempotency contract:** routine HTTP retries would create duplicate inbox
  entries.
