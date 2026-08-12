# AgentPost Protocol

Version: 0.1 (initial implementation baseline)

## 1. Scope

AgentPost is a persistent, asynchronous agent-to-agent messaging protocol. It
defines identity, addressing, authentication, message submission, durable inbox
retrieval, explicit state transitions, replies, attachments, directory lookup,
authorization errors, and delivery receipts. It does not interpret or execute the
business meaning of a message.

Version 0.1 is a single-server/local-registry, single-recipient MVP. One server
may register addresses from multiple domains, but it does not route across
servers. The receiver is assumed to be offline. Federation, multi-recipient
delivery, realtime transports, workflow execution, and LLM routing are outside
this version. The address, envelope, and delivery model deliberately leave room
for those capabilities.

Normative terms **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are
used as requirement keywords.

## 2. Transport and media type

- The API base path is `/api/v1`.
- Production deployments MUST use HTTPS. Plain HTTP is permitted only for local
  development.
- JSON request and response bodies use `application/json` and UTF-8.
- Binary attachment upload and download use the attachment endpoint rather than
  base64 inside a message.
- Clients SHOULD send `Accept: application/json` for JSON resources.
- Every response SHOULD include `X-Request-ID`; clients MAY supply one, but the
  server MUST validate or replace an unsuitable value.

REST polling is the v0.1 delivery mechanism. Later SSE, WebSocket, webhook, and
push transports are only accelerators: PostgreSQL and the persistent inbox remain
authoritative.

## 3. Identity and authentication

An Agent has two distinct identifiers:

- `agent_id`: immutable UUID used as the system identity;
- `address`: canonical, human-readable address such as
  `alice@agents.local`.

An address is normalized to lowercase and contains a local component and an
explicit domain. `display_name` is mutable presentation data and MUST NOT be used
as an identity key. Clients MUST treat all IDs as opaque values even when the MVP
uses UUIDs internally.

Agent endpoints authenticate with:

```http
Authorization: Bearer agt_<secret>
```

The server MUST derive `sender_agent_id` from the authenticated API key. A message
submission MUST NOT be allowed to select an arbitrary sender through a `from`,
`sender_agent_id`, metadata, or body field. If a strict request body contains an
unknown sender-like field, the server SHOULD reject it as invalid input rather
than ignore it.

API keys are secrets. They MUST be shown only at creation (or a future rotation)
time, stored as a keyed digest rather than plaintext, excluded from logs, and
revocable. The v0.1 data model supports revocation, but the MVP exposes no
self-service rotate/revoke endpoint.

## 4. Canonical message envelope

The version-controlled JSON Schema is
[`schemas/message-envelope-v0.1.json`](schemas/message-envelope-v0.1.json). The
schema describes the canonical server-issued message envelope. Fields marked
`readOnly` are produced or bound by the server; the message-create request uses
the writable subset described below.

```json
{
  "spec_version": "0.1",
  "message_id": "msg_01K123EXAMPLE",
  "from": {
    "agent_id": "33d7223f-f90e-4ccf-9ca8-71d156891687",
    "address": "alice@agents.local"
  },
  "to": [
    {
      "agent_id": "bd260abe-6f30-4e41-86a6-d79d48ba0676",
      "address": "bob@agents.local"
    }
  ],
  "type": "task",
  "subject": "Analyse the attached report",
  "content": {
    "format": "markdown",
    "body": "Please analyse report.pdf.",
    "security_label": "external_agent_content"
  },
  "task": {
    "instruction": "Analyse report.pdf",
    "deadline": null,
    "expected_output": "markdown report"
  },
  "attachments": [],
  "thread_id": "579fb4ce-c33b-4f9f-a6e4-61f416d46843",
  "reply_to": null,
  "priority": "normal",
  "requires_ack": true,
  "metadata": {},
  "created_at": "2026-08-12T08:00:00Z",
  "expires_at": null
}
```

The v0.1 `to` field is an array for forward compatibility but MUST contain exactly
one recipient. A later protocol version can raise this limit without replacing
the envelope shape or delivery-record abstraction.

All received message content is labelled `external_agent_content`. A receiver
MUST treat the body, structured task/result fields, metadata, filenames, and
attachments as untrusted external input. A message type named `system` does not
turn its body into a model system instruction and does not grant elevated tool
permissions.

The standard message types are:

| Type | Intended use |
| --- | --- |
| `message` | General information |
| `task` | Work requested from another Agent |
| `result` | Outcome of a prior task; requires `reply_to` |
| `request` | Structured request that is not a delegated task |
| `response` | Response to a request |
| `notification` | Informational notice |
| `event` | Occurrence for machine consumption |
| `error` | Business-level error reported by an Agent |
| `system` | AgentPost service notice, still untrusted by model runtimes |

`metadata` is application-defined and non-authoritative. Identity, authorization,
routing, expiry, state transitions, and attachment access MUST NOT be derived from
untrusted metadata.

Delivery state is a mutable per-recipient projection and is intentionally not part
of the canonical immutable envelope. Message-resource responses pair the envelope
with a delivery representation containing `status`, recipient identity, and the
applicable `delivered_at`, `read_at`, and `acked_at` timestamps. The MVP has one
such delivery; the separation remains valid when multi-recipient delivery arrives.

## 5. Message creation and acceptance

### 5.1 Create request

```http
POST /api/v1/messages
Authorization: Bearer agt_<alice-secret>
Idempotency-Key: alice-job-20260812-001
Content-Type: application/json

{
  "to": [{"address": "bob@agents.local"}],
  "type": "message",
  "subject": "Hello Bob",
  "content": {
    "format": "text",
    "body": "Hello Bob"
  },
  "attachments": [],
  "priority": "normal",
  "requires_ack": true,
  "metadata": {},
  "expires_at": null
}
```

The server validates the request and authenticates the sender. The messaging
service first checks whether the sender-scoped idempotency record already names a
matching committed message. For a new operation, it resolves and locks the one
local recipient, enforces inbound ACLs, creates the message, delivery, and
idempotency record, binds eligible uploads, appends an audit event, and commits
those records in one database transaction. Responses add the
`external_agent_content` content label.

A successful local submission returns `201 Created` for the first request and the
canonical message resource plus its single delivery projection. The following is
an abbreviated response excerpt. Because local delivery is committed in the same
transaction, `delivery.status` is already `delivered`:

```json
{
  "message_id": "msg_01K123EXAMPLE",
  "thread_id": "579fb4ce-c33b-4f9f-a6e4-61f416d46843",
  "accepted_at": "2026-08-12T08:00:00Z",
  "delivery": {
    "status": "delivered",
    "delivered_at": "2026-08-12T08:00:00Z"
  }
}
```

The response means the transaction committed to durable storage; it does not mean
the receiver is online, has read the content, or has processed it. A server MUST
NOT return acceptance if that transaction rolled back.

### 5.2 Idempotency

Reliable send clients MUST provide `Idempotency-Key` on message creation and
replies. A key is scoped to the authenticated sender. The server maintains a
uniqueness constraint on `(sender_agent_id, idempotency_key)` and stores a digest
of the normalized request.

- First use: execute the transaction and retain the resulting resource reference.
- Same sender, same key, same request digest: return the original message and
  receipt without creating a second message or delivery. The replay response MAY
  use `200 OK` and SHOULD carry `Idempotency-Replayed: true`.
- Same sender, same key, different request digest: return `409 Conflict` with
  `IDEMPOTENCY_CONFLICT`.
- The same key used by a different authenticated sender is independent.

Clients MUST deduplicate received work by `message_id`; ACK is the application
receipt and is not an exactly-once execution guarantee.

## 6. Persistent inbox and retrieval

```http
GET /api/v1/inbox?status=unread&type=task&limit=50&cursor=<opaque>
Authorization: Bearer agt_<bob-secret>
```

Inbox access is always scoped to the authenticated Agent. The server MUST reject
attempts to select another Agent's inbox. Supported filters include `status`,
`sender`, `type`, `priority`, `since`, and `limit`.

`unread` is a query classification meaning delivered but neither explicitly read
nor acknowledged; it is not an additional lifecycle state. Each delivery receives
a durable monotonic `inbox_seq`. Pagination uses an opaque, HMAC-protected cursor
binding the authenticated Agent, normalized filters, and last sequence boundary.
Clients MUST NOT construct or modify cursors. An invalid or filter-incompatible
cursor returns `400 INVALID_CURSOR`. v0.1 cursors have no time-based expiration;
operators must preserve the signing secret across restarts.

A response contains messages and an optional next cursor:

```json
{
  "items": [],
  "next_cursor": null,
  "has_more": false
}
```

```http
GET /api/v1/messages/{message_id}
Authorization: Bearer agt_<secret>
```

Fetching an inbox page or message MUST NOT mark it read. A sender may retrieve a
message it sent to inspect delivery state; a recipient may retrieve a message in
its inbox. Other Agents receive `404 MESSAGE_NOT_FOUND` rather than an existence
leak.
Consequently, after Bob ACKs a message, Alice's authenticated
`GET /api/v1/messages/{message_id}` returns the same envelope with a delivery
projection whose status is `acked`.

## 7. Lifecycle and explicit transitions

The conceptual lifecycle is:

```text
created -> accepted -> delivered -> read -> acked
                         |            |
                         +----------->+

terminal exceptions: rejected | failed | expired
```

Only `delivered`, `read`, and `acked` are active external Delivery states for
local v0.1. `created` and `accepted` are conceptual pre-commit phases. A rejected
request is an HTTP refusal rather than a stored Inbox state; `failed` and
`expired` are database values reserved for future remote-delivery and retention
workers.

| State | Meaning |
| --- | --- |
| `created` | Client-local or pre-transaction representation; not a durability promise |
| `accepted` | Validation, authorization, and durable acceptance are being/successfully completed |
| `delivered` | Committed to the recipient's persistent inbox |
| `read` | Recipient explicitly marked the message read |
| `acked` | Recipient explicitly confirmed receipt or processing |
| `rejected` | Server refused the message before acceptance |
| `failed` | An accepted delivery could not be completed; primarily reserved for later remote delivery |
| `expired` | Reserved terminal state for a future expiry/retention worker |

For local v0.1 delivery, `accepted` may exist only inside the transaction and the
first externally visible durable state is normally `delivered`. State transitions
are monotonic and idempotent. `delivered -> acked` is allowed as one explicit ACK
operation; the server atomically fills a missing `read_at`, so `acked_at` can never
exist without `read_at`. A later read request MUST NOT regress an acknowledged
message or overwrite the first read timestamp.

Explicit read:

```http
POST /api/v1/messages/{message_id}/read
Authorization: Bearer agt_<recipient-secret>
```

Explicit ACK:

```http
POST /api/v1/messages/{message_id}/ack
Authorization: Bearer agt_<recipient-secret>
```

Only the recipient can make these transitions. Repeating either request returns
the current representation without duplicating audit effects that are intended to
be unique. `delivered_at`, `read_at`, and `acked_at` are server timestamps; a
client-supplied timestamp is non-authoritative.

The MVP validates that a supplied `expires_at` is in the future but does not run
an expiry or retention worker. It therefore does not transition deliveries to
`expired` automatically.

## 8. Replies and threads

```http
POST /api/v1/messages/{message_id}/reply
Authorization: Bearer agt_<recipient-secret>
Idempotency-Key: bob-reply-20260812-001
Content-Type: application/json
```

The reply body accepts message content, type, subject, attachments, priority,
acknowledgement preference, metadata, and expiry. The server derives the sender
from authentication, derives the target from the original conversation, sets
`reply_to` to the referenced message, and inherits its `thread_id`. A caller MUST
NOT use reply fields to substitute a new sender or arbitrary recipient.

```http
GET /api/v1/threads
GET /api/v1/threads/{thread_id}
```

Thread history is ordered deterministically by creation time and message ID.
Access requires the authenticated Agent to participate in at least one message in
the thread. An inaccessible thread returns `404 THREAD_NOT_FOUND`.

A `result` message MUST be a reply to its originating task. Attachments such as
`analysis.md` are normal private attachments bound to the result message.

## 9. Attachments

Message bodies contain attachment metadata, never large base64 payloads.

```http
POST /api/v1/attachments
Authorization: Bearer agt_<secret>
Content-Type: multipart/form-data

GET /api/v1/attachments/{attachment_id}
Authorization: Bearer agt_<secret>
```

The upload service generates the storage key, computes SHA-256, records byte size
and media type, and returns an attachment ID. A sender then references an eligible
unbound upload when creating a message. Clients never choose or receive a raw
filesystem path. The service MUST enforce configured size limits, reject unsafe
filenames and path traversal, prevent binding another Agent's upload, and allow
downloads only to authorized message participants.

The database owns attachment metadata and authorization relationships. v0.1 uses
private filesystem storage behind an object-storage interface; an S3-compatible
implementation may replace it without changing message metadata.

## 10. Directory and Agent resources

```text
POST  /api/v1/agents
GET   /api/v1/agents/{id}
GET   /api/v1/agents/by-address/{url-encoded-address}
PATCH /api/v1/agents/{id}
GET   /api/v1/directory/search?q=bank
GET   /api/v1/directory/search?capability=financial-research
```

Capabilities are structured strings, not display-name parsing. Directory results
are discovery candidates, not proof that an Agent is online, trusted, available,
or verified for a task. Agent registration and API-key generation are deployment
policy decisions and MAY require an administrator even when a debug UI exposes
them locally.

## 11. Inbound permissions

The MVP supports inbound policy modes `public`, `allowlist`, `contacts_only`, and
`private`. `contacts_only` means an earlier local message exists in either
direction between the two Agents. Rules may allow or block specific canonical
Agent addresses or domains. An explicit block always wins over an allow rule.
Authorization is evaluated for every send and reply and audited. A later policy
change does not silently delete messages that were already accepted.

```text
GET    /api/v1/agents/{agent_id}/access-policy
PUT    /api/v1/agents/{agent_id}/access-policy
POST   /api/v1/agents/{agent_id}/access-rules
DELETE /api/v1/agents/{agent_id}/access-rules/{rule_id}
```

These endpoints are self-service: the authenticated Agent can manage only its
own policy and rules. Another Agent receives a non-enumerating `404`.

A blocked or disallowed send returns `403 DELIVERY_NOT_ALLOWED`. The response
SHOULD avoid disclosing private ACL contents.

## 12. Error model

Non-success responses use one stable envelope:

```json
{
  "error": {
    "code": "IDEMPOTENCY_CONFLICT",
    "message": "The idempotency key was already used for a different request.",
    "request_id": "req_01K123EXAMPLE",
    "details": {}
  }
}
```

`code` is machine-stable; `message` is human-oriented and MUST NOT be parsed.
`details` MUST NOT disclose API-key material, private ACLs, attachment storage
paths, or the existence of another Agent's private object.

| HTTP | Code | Meaning |
| --- | --- | --- |
| `400` | `INVALID_IDEMPOTENCY_KEY` | Required idempotency key is invalid |
| `400` | `INVALID_CURSOR` | Cursor is malformed, invalidly signed, or incompatible with the query |
| `401` | `INVALID_API_KEY` | Bearer token is absent, invalid, or revoked |
| `403` | `DELIVERY_NOT_ALLOWED` | Sender is blocked or not permitted by recipient policy |
| `404` | resource-specific `*_NOT_FOUND` | Resource is absent or inaccessible to the authenticated Agent |
| `409` | `IDEMPOTENCY_CONFLICT` | Same sender/key was used for a different normalized request |
| `409` | `INVALID_STATE_TRANSITION` | Requested operation cannot legally follow current state |
| `413` | `ATTACHMENT_TOO_LARGE` | Upload exceeds configured size limit |
| `422` | `SCHEMA_VALIDATION_FAILED` | JSON is malformed or the body/query violates its schema |
| `503` | `DATABASE_UNAVAILABLE` | Readiness cannot reach the durable database |

Rate limiting is not implemented by the MVP. A future implementation reserves
`429 RATE_LIMITED` but MUST document retry behavior before enabling it.

Authentication failure is distinct from authorization failure. For object reads,
`404` is used for both absent and inaccessible resources to limit enumeration.

## 13. Delivery semantics

AgentPost v0.1 targets **at-least-once transport with application-level
deduplication**, not distributed exactly-once execution.

- A committed local message has one durable message record and one recipient
  delivery record.
- An HTTP retry can replay the acceptance response; sender-scoped idempotency
  prevents it from creating duplicate messages.
- A client may observe the same message across polls until it advances state or
  changes its cursor; it deduplicates by `message_id`.
- ACK records explicit receipt/processing but cannot prove that downstream tools
  ran exactly once.
- Server restart cannot erase a committed message because PostgreSQL is the
  source of truth and attachment storage is persistent.

If the sender receives no successful acceptance response, the outcome is unknown;
it SHOULD retry with the same idempotency key. Retrying with a new key can create a
new message.

## 14. Observability and operational endpoints

```text
GET /health
GET /ready
```

`/health` reports process liveness. `/ready` reports whether required durable
dependencies, especially PostgreSQL, are usable. Structured logs and audit events
include relevant `request_id`, `message_id`, `agent_id`, and `thread_id`. The
standard HTTP logger records only allowlisted operational fields and an exception
type, never exception text or traceback. Logs and audit records MUST exclude full
API keys, secrets, message/attachment bodies, and raw private storage paths.
Reverse-proxy and hosting logs are separate operator-controlled surfaces and
require the same redaction policy.

The optional `/admin` console and `/api/v1/admin/*` operational endpoints are not
Agent protocol resources. They are disabled unless a separate Admin token is
configured, and they MUST NOT return message bodies, API-key digests, or storage
paths. Production deployments MUST put the console behind HTTPS and an additional
trusted network or identity boundary where appropriate.

## 15. Compatibility and evolution

The v0.1 write API does not expose version negotiation: create/reply request
schemas omit `spec_version`, and server-issued message resources always report
`spec_version: "0.1"`. Unknown request fields are rejected through normal schema
validation. A later negotiated version MUST define its version field/header and a
stable incompatibility error before accepting multiple versions. Additive optional
fields require a documented schema revision. Clients MUST NOT infer federation
support merely because an address has a remote domain.

Future federation can discover a domain endpoint, authenticate server-to-server,
and create a delivery on the recipient server. Stable addresses, opaque message
IDs, versioned envelopes, and separate delivery records allow that evolution
without removing the persistent inbox abstraction. A2A and MCP compatibility are
adapters to this protocol, not replacements for it.
