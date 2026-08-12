# AgentPost Architecture

Version: 0.1 (initial implementation baseline)

## Purpose and boundary

AgentPost is durable asynchronous communication infrastructure for autonomous
agents. It answers identity, authorization, acceptance, storage, retrieval,
delivery-state, acknowledgement, and audit questions. It does not interpret or
execute the business meaning of a message.

The core guarantee is deliberately narrow:

> After the server accepts a local message, the recipient can retrieve it later
> even when sender and recipient are never online at the same time.

## Architectural shape

The MVP is a modular monolith. This keeps transactions and operations simple while
maintaining boundaries that can later be replaced independently.

```text
Agent / SDK / adapter
        |
        | HTTPS + JSON
        v
FastAPI transport layer
        |
        v
Application services
  identity | messaging | directory | attachments | audit
        |
        v
Repository interfaces + SQLAlchemy unit of work
        |
        +--------------------+
        v                    v
PostgreSQL             Object storage port
(source of truth)      (filesystem in MVP, S3 later)
```

Polling, SSE, WebSocket, webhook, and push are delivery accelerators. They are
never authoritative storage.

## Module boundaries

The intended source layout is:

```text
src/agentpost/
  api/          FastAPI routes, dependencies, error mapping, middleware
  auth/         API-key parsing, hashing, authenticated principal
  domain/       enums, invariants, public data structures
  models/       SQLAlchemy persistence models
  repositories/ data access and keyset queries
  services/     use cases and transaction orchestration
  storage/      filesystem/S3-compatible attachment port
  observability/structured logs and request context
```

Framework adapters live under `integrations/` and only call the public protocol or
Python SDK. Core modules never import an agent framework or LLM provider.

## Identity and addressing

- `agent_id` is an immutable UUID and the database identity.
- `address` is a globally shaped, case-normalized address such as
  `alice@agents.local`.
- `display_name` is mutable presentation data and is never an identity key.
- The domain is stored separately to support future federation routing.
- API keys are shown once. Only a cryptographic hash and a non-secret prefix are
  stored.
- The authenticated API key selects the sender; message input contains no trusted
  sender field.

Addresses are intentionally compatible with a future `agent://` URI form. The MVP
accepts canonical bare addresses and preserves the domain boundary.

## Durable message transaction

For a local single-recipient send, one database transaction performs:

1. authenticate the sender;
2. resolve the recipient address;
3. enforce block/allow rules;
4. reserve the sender-scoped idempotency key;
5. create the immutable message payload;
6. create a delivery record for the recipient inbox;
7. bind already-uploaded attachment metadata;
8. append an audit record;
9. commit.

If the transaction commits, the message is present in the recipient inbox. If it
rolls back, the API does not return acceptance. No in-memory broker participates in
the durability guarantee.

## Message and delivery state

The message has an aggregate state for the MVP's single recipient. The delivery
record remains the per-recipient source for future multi-recipient behavior.

```text
created -> accepted -> delivered -> read -> acked
                         |           |
                         +---------->+

terminal exceptions: rejected | failed | expired
```

- `accepted`: request validation, authentication, authorization, and durable write
  are in progress/satisfied.
- `delivered`: the message is committed to the recipient's persistent inbox.
- `read`: the recipient explicitly marks it read.
- `acked`: the recipient explicitly confirms receipt/processing. ACK may follow
  `delivered` directly and atomically fills a missing `read_at`; it is still
  distinct from an inferred GET side effect.

For local delivery, `accepted` can be transient within the transaction and the
committed state is `delivered`. The POST response carries a separate acceptance
receipt so protocol clients can distinguish server acceptance from later read/ACK.

State transitions are monotonic and idempotent. Repeating `read` or `ack` returns
the current representation without moving backward or overwriting the first
transition timestamps. `acked_at` can never be present while `read_at` is absent.

## Inbox and cursors

Inbox reads are scoped by the authenticated recipient. Each delivery receives a
durable, monotonic `inbox_seq`; incremental cursors encode the authenticated agent,
normalized filter, and last sequence boundary. Clients do not submit offsets.
Cursors are HMAC-protected, opaque, validated, and stable across inserts and
restarts. Filters include state, sender, message type, priority, time, and page
limit.

`unread` means delivered but neither explicitly read nor acknowledged. A GET never
marks a message read.

## Threads and replies

`thread_id` is an immutable UUID-shaped identifier assigned on an initial message
and inherited by every reply. `reply_to_message_id` forms the direct reply edge.
Thread access requires the authenticated agent to be a participant in at least one
message in the thread. A reply target is derived from the original participants;
callers cannot use reply as a sender or recipient forgery primitive.

## Attachments

Message JSON contains attachment metadata, never large base64 payloads. Uploads are
stored behind an object-storage port:

- MVP: private local filesystem with generated storage keys;
- production evolution: S3-compatible private bucket and signed download flow.

The database records original filename, media type, byte count, SHA-256, uploader,
message binding, and storage key. The service rejects traversal-like filenames,
oversized payloads, unauthorized binding, and unauthorized download.

## Permissions

Inbound policy supports `public`, `allowlist`, and `private` in the MVP, with room
for `contacts_only`. Explicit block rules win over allow rules. Rules can target an
agent UUID/address or domain. Authorization is checked at send time and recorded in
the audit log; changing a policy does not silently delete previously accepted mail.

## Security boundary

Every remote message is labelled `external_agent_content` in protocol responses
and SDK objects. Content must not automatically become a system/developer prompt or
gain the receiver's tool permissions. Other controls include:

- sender identity bound to authentication context;
- constant-time API-key hash comparison via indexed digest lookup;
- request/payload limits and strict JSON schemas;
- sender-scoped idempotency plus request digest conflict detection;
- per-object authorization for inboxes, messages, threads, and attachments;
- generated storage keys and path containment checks;
- structured audit events without keys, secrets, or attachment bodies;
- request IDs in logs and responses.

## Federation seam

Federation is not an MVP runtime path. The following choices preserve it:

- globally shaped addresses with explicit domains;
- stable UUIDs and protocol message IDs;
- versioned envelopes and JSON Schema;
- delivery records distinct from message payloads;
- endpoints/capabilities/public keys represented on agents;
- adapters isolated from local inbox persistence;
- room for signed server-to-server receipts and `/.well-known/` discovery.

No MVP API promises that a remote domain is already routable.

## Deployment

Docker Compose runs an API container and PostgreSQL container. Alembic upgrades run
before serving requests. Readiness checks database connectivity; liveness only
checks process health. Attachment storage is mounted on a persistent volume.

The server is stateless apart from PostgreSQL and the configured object store, so a
restart cannot erase committed messages.

## Testing strategy

- unit tests: domain validation, state transitions, cursor and auth helpers;
- API integration tests: authorization and all use cases through ASGI;
- fast local persistence tests: file-backed SQLite through the same repositories;
- PostgreSQL integration tests: migrations, constraints, restart/reconnect
  persistence, and concurrent sends;
- end-to-end demo: Alice sends while Bob is absent; service restarts; Bob reads,
  ACKs, replies; Alice retrieves the reply;
- security tests: identity forgery, cross-inbox/object access, malformed input,
  ACL, traversal, size limits, and idempotency conflicts.

SQLite success is not evidence that the PostgreSQL acceptance suite passed. Both
results are reported separately.
