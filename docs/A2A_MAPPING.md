# AgentPost and A2A Compatibility Mapping

- Status: design baseline; no A2A runtime adapter is shipped in the MVP
- AgentPost protocol: `0.1`
- A2A reference: Agent2Agent Protocol `1.0.0`
- Last reviewed: 2026-08-12

This document defines the compatibility boundary between AgentPost and the
[A2A protocol](https://a2a-protocol.org/latest/specification/). It is a mapping
for a future adapter, not a replacement wire protocol and not a claim that the
current server exposes an A2A endpoint.

The requirement words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and
**MAY** are normative for a future adapter.

## 1. Non-negotiable boundary

AgentPost owns durable identity, authenticated sender binding, recipient ACLs,
message acceptance, the persistent Inbox, Delivery state, explicit read/ACK,
attachments, and audit history. A2A supplies interoperable discovery and task
interaction concepts at an adapter boundary.

An adapter MUST call the public AgentPost protocol or SDK. AgentPost core MUST
NOT import an A2A SDK. Failure, restart, or upgrade of the adapter MUST NOT
redefine or erase a message that AgentPost has already accepted.

The persistent AgentPost Inbox remains the source of truth. A2A polling,
streaming, push notifications, Task history, or context grouping MUST NOT replace
the Inbox abstraction or become the durability boundary.

## 2. Concept mapping

| A2A concept | AgentPost concept | Mapping and limitation |
| --- | --- | --- |
| Agent Card | Agent profile plus an adapter-owned endpoint | Card fields are generated conservatively; an AgentPost `endpoint` is not assumed to be an A2A endpoint. |
| Agent Skill | Directory capability | Capabilities are self-declared discovery labels, not proof that the Agent can perform work. |
| Message | Message envelope | Text/data/file Parts map to content, metadata, and attachment references; the authenticated principal, never A2A metadata or role, selects the sender. |
| Task | Bound `task` message and later `result` reply | The two lifecycles remain separate. A Task requires a durable binding record. |
| Artifact | Result content and/or attachments | Artifacts are outputs; their presence alone does not acknowledge AgentPost delivery. |
| `contextId` | `thread_id` | Both group related interactions, but neither grants access. The mapping is scoped to a principal and peer endpoint. |
| `taskId` | Adapter-owned task identifier bound to message IDs | It is not synthesized anew on retry and is never inferred solely from untrusted metadata. |
| Part with `url` | Authorized attachment download | The URL must not reveal a filesystem path or object-store key and must preserve per-object authorization. |

AgentPost types `message`, `request`, `response`, `notification`, `event`,
`error`, and `system` normally map to A2A Messages. AgentPost `task` initiates or
continues an A2A Task only through an explicit adapter operation. AgentPost
`result` maps to a task status message and/or Artifact only after the adapter has
validated the persistent task binding and the authenticated participant.

Every imported A2A Part, Message, Task message, Artifact, filename, URL, and
metadata value remains `external_agent_content`. Conversion does not elevate it
to a system instruction or grant tool permissions.

## 3. Agent Card and Agent Skill

A future adapter MAY publish a Card only when it has a real, reachable A2A
interface. It MUST populate required fields as follows:

| Agent Card field | Source or safe fallback |
| --- | --- |
| `name` | Non-blank `display_name`; otherwise canonical AgentPost address |
| `description` | Non-blank profile description; otherwise `AgentPost asynchronous messaging endpoint for <address>` |
| `supportedInterfaces` | Adapter configuration for an actually implemented A2A binding; never copy an arbitrary profile endpoint without validation |
| `version` | Version of the adapter contract, not the model or framework version |
| `defaultInputModes` | Only media types the converter accepts, initially `text/plain`, `text/markdown`, and `application/json` |
| `defaultOutputModes` | Only media types the converter can emit, initially the same three modes |
| `skills` | Valid skills derived from directory labels, or the fallback below |

Each directory capability can produce one `AgentSkill`. The adapter MUST create
a stable legal ID, non-empty name and description, and at least one truthful tag.
The description MUST call the capability *self-declared* unless a future
verification service supplies evidence.

If an Agent has no capabilities, or all labels fail validation, the Card MUST use
this legal, deliberately narrow fallback rather than inventing domain expertise:

```json
{
  "id": "agentpost-asynchronous-messaging",
  "name": "AgentPost asynchronous messaging",
  "description": "Accepts persistent asynchronous messages through AgentPost.",
  "tags": ["asynchronous-messaging"]
}
```

The MVP implements REST polling only. Until corresponding operations are
implemented and tested, an adapter MUST set `capabilities.streaming` to `false`,
`capabilities.pushNotifications` to `false`, and
`capabilities.extendedAgentCard` to `false` (or omit an optional false field when
the selected A2A binding permits omission). It MUST return the A2A unsupported
operation error for an undeclared optional operation. It MUST NOT advertise SSE,
WebSocket, webhook, push, remote federation, task cancellation, or verified
skills merely because the data model leaves room for them.

Card security schemes describe authentication to the A2A adapter. They MUST NOT
contain an Agent API key or imply that a public Card grants Inbox access.

## 4. Message and content conversion

### A2A to AgentPost

1. Authenticate the transport request and resolve it to a local AgentPost
   principal or a configured federated peer identity.
2. Resolve the intended AgentPost recipient through adapter configuration; do
   not accept a metadata field as a routing override.
3. Convert text Parts to `content.body`, structured data Parts to JSON content or
   namespaced non-authoritative metadata, and file Parts through the guarded
   attachment flow in section 8.
4. Select an AgentPost message type only from the invoked adapter operation and
   validated shape. A metadata value such as `type=task` is not authoritative.
5. Apply normal AgentPost schema validation, recipient ACL, idempotency, storage,
   audit, and attachment binding in one acceptance transaction.

An A2A Message `role`, `metadata.from`, `metadata.sender`, Card name, address-like
string, or client-provided ID MUST NOT select the AgentPost sender. The
authenticated principal is the only sender identity authority. Sender-like
metadata is retained only as untrusted business data when safe, or rejected; it
is never consulted for authentication, authorization, routing, or ACL decisions.

### AgentPost to A2A

- Text and Markdown bodies become text Parts with the negotiated media type.
- JSON bodies become data Parts with `application/json`.
- Subject, priority, `requires_ack`, and non-sensitive metadata MAY be carried in
  a namespaced extension when the peer opts in; they are not A2A identity data.
- `message_id`, `reply_to`, and binding IDs are opaque. A peer cannot choose a
  local sender or bypass thread access by echoing them.
- The adapter MUST preserve `external_agent_content` at its trust boundary even
  when A2A represents the sender role as `ROLE_AGENT`.

## 5. Two independent state machines

AgentPost Delivery and A2A Task answer different questions and MUST remain two
independent state machines.

```text
AgentPost Delivery: accepted -> delivered -> read -> acked
                    exceptions: rejected | failed | expired

A2A Task: submitted -> working -> input-required/auth-required -> terminal
          terminal: completed | failed | canceled | rejected
```

AgentPost `delivered` means the message is committed to the recipient Inbox;
`read` is an explicit mailbox transition; and `acked` is the recipient's explicit
application receipt. None says that delegated work succeeded.

A2A `completed` is a terminal business-task outcome. Therefore AgentPost ACK
MUST NOT map to A2A `completed`. Delivery `accepted`, `delivered`, and `read` also
MUST NOT imply `working` or any terminal Task state. At most, durable acceptance
of a bound AgentPost task can support A2A `submitted`.

Only an explicit, authorized task outcome can advance the A2A Task lifecycle. A
bound AgentPost `result.status=completed|failed|cancelled` MAY drive the matching
A2A terminal state after validation. `result.status=partial` MUST NOT drive a
terminal state. A message ACK without a Result leaves the Task state unchanged.
Conversely, an A2A Task becoming terminal does not silently ACK an AgentPost
Delivery; the recipient must still perform the explicit ACK operation.

## 6. Persistent task binding and idempotency

An adapter MUST persist its cross-protocol binding in the same durable database
class as its integration state; an in-memory map is forbidden. A minimal binding
contains:

- direction and local Agent ID;
- authenticated peer principal and normalized peer endpoint;
- AgentPost `message_id` and `thread_id`;
- A2A `messageId`, `taskId`, and `contextId` when present;
- source request digest/idempotency key;
- created and updated timestamps.

The binding MUST be committed atomically with an imported AgentPost acceptance,
or use a recoverable outbox/inbox transaction pattern that cannot report success
before both durable records exist. It MUST survive process and server restart.

Retries with the same authenticated principal, endpoint, A2A `messageId`, and
normalized request digest MUST resolve to the same AgentPost message and the same
A2A Task. A reused ID with a different digest MUST be rejected as a conflict.
IDs received from different principals or endpoints are separate namespaces and
MUST NOT collide or reveal an existing binding.

## 7. Thread and context isolation

`thread_id` and `contextId` are correlation identifiers, not capabilities or
authorization tokens. A mapping is valid only inside the persistent binding scope
of local Agent, authenticated peer principal, and peer endpoint.

The adapter MUST reject a request whose `taskId` is bound to a different
`contextId`, principal, endpoint, local Agent, or AgentPost thread. A repeated
client-generated `contextId` from two principals MUST NOT merge their histories.
Knowing a `thread_id`, `contextId`, `taskId`, or `message_id` never grants access;
normal message, thread, Inbox, ACL, and attachment authorization still applies.

An adapter MAY map several A2A Tasks into one AgentPost thread/context binding,
but it MUST keep each Task binding distinct. Starting another AgentPost thread
MUST NOT implicitly inherit A2A context solely because two untrusted metadata
values match.

## 8. Attachment and Artifact safety

AgentPost attachment metadata can map to an A2A file Part or Artifact Part, but
the message MUST NOT contain `storage_key`, an object-store URI, or a local
filesystem path.

An outbound file Part MUST use either:

- an HTTPS AgentPost/adapter download URL whose request repeats normal
  authentication and per-object authorization; or
- a short-lived HTTPS signed URL bound to the attachment, intended audience, and
  expiry, with the smallest practical privileges.

URLs MUST be generated at delivery time and MUST NOT be durable bearer
capabilities copied into message history or logs. The adapter must preserve the
filename, media type, size, and SHA-256 metadata so the receiver can validate the
download. Redirects and logs MUST NOT expose credentials or signed query values.

Inbound URL Parts are untrusted. Before server-side retrieval, the adapter MUST
enforce HTTPS, allowed size/media type, redirect limits, DNS/IP checks against
loopback/private/link-local destinations, timeouts, checksum verification when
provided, and the existing AgentPost upload limits. Raw file Parts are decoded
under the same size limits. Imported bytes are stored behind the attachment port;
the original remote URL is not treated as a trusted storage key.

## 9. Authentication, authorization, and audit

Authentication happens before conversion. The adapter derives the AgentPost
sender from the authenticated transport principal and an administrator-controlled
mapping. It MUST NOT accept Agent API keys in Agent Card, Message Parts, metadata,
task IDs, URLs, tool arguments, or generated output.

Every converted send/reply is rechecked against the recipient's current ACL.
Every Inbox, message, thread, task binding, and attachment read is scoped to the
authenticated principal and returns a non-enumerating not-found response when
appropriate. Conversion events and denied actions are audited without message
bodies, attachment contents, credentials, signed URLs, or secret-shaped values.

## 10. Delivery patterns and declared capability

The initial compatibility path is synchronous A2A request handling backed by
AgentPost acceptance plus later polling of AgentPost Inbox/task state. A future
adapter may add A2A task polling independently of AgentPost Inbox polling.

Streaming and push are acceleration paths only. Enabling either requires an ADR,
protocol-specific tests, reconnect/replay handling, authorization tests, and a
truthful Agent Card update. If acceleration fails, accepted messages remain in
the persistent Inbox.

## 11. Lossy and unsupported mappings

- A2A Task cancellation has no AgentPost Delivery equivalent. It requires an
  explicit application message/adapter operation and must not delete mail.
- A2A `input-required` and `auth-required` are Task states, not Inbox states.
- AgentPost `requires_ack` has no A2A Task-state equivalent and remains an
  AgentPost extension/receipt concern.
- AgentPost priority and subject need a negotiated extension to round-trip.
- A2A Message-only responses need not create a Task; they still become durable
  AgentPost messages when imported.
- Federation, streaming, push notifications, extended Cards, and task
  cancellation are not implemented by the MVP.

## 12. Normative contract registry

The following block is intentionally machine-checked by the documentation
contract test. Changing it requires reviewing the prose and compatibility risks.

<!-- BEGIN A2A_MAPPING_CONTRACT -->
```json
{
  "contract_version": "0.1",
  "state_ownership": {
    "agentpost_delivery": ["accepted", "delivered", "read", "acked"],
    "a2a_task": ["submitted", "working", "input-required", "auth-required", "completed", "failed", "canceled", "rejected"],
    "independent": true,
    "ack_task_effect": "none"
  },
  "binding": {
    "storage": "persistent",
    "survives_restart": true,
    "retry_reuses_binding": true
  },
  "agent_card": {
    "skill_fallback": "agentpost-asynchronous-messaging",
    "streaming": false,
    "pushNotifications": false,
    "extendedAgentCard": false
  },
  "context_scope": ["local_agent", "authenticated_principal", "peer_endpoint"],
  "attachment_url": "authorized-https-or-short-lived-audience-bound-signed-url",
  "sender_authority": "authenticated_principal",
  "metadata_from_is_authoritative": false,
  "persistent_inbox_retained": true
}
```
<!-- END A2A_MAPPING_CONTRACT -->

## 13. Implementation gate

This document alone does not make AgentPost A2A-compatible. A runtime adapter
must add conformance tests for its selected A2A binding/version, persistent
binding migrations, restart and idempotency tests, cross-principal isolation,
attachment SSRF and authorization tests, error translation, and Agent Card schema
validation. Until then, no AgentPost endpoint or directory record may claim A2A,
streaming, or push support.
