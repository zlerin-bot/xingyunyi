# 星云驿 Project Status

Last updated: 2026-08-17

## Current state

This repository started as an empty directory. There was no existing application,
package manifest, test suite, database model, or Git history to reuse.

The MVP implementation is locally runnable as a protocol-first modular monolith:

- FastAPI HTTP service
- SQLAlchemy 2.x persistence layer
- PostgreSQL as the production source of truth
- Alembic migrations
- local filesystem attachment adapter with an S3-compatible boundary
- framework-neutral REST/JSON protocol
- Python SDK, optional OpenClaw/MCP adapters, and an A2A compatibility mapping
- 星轨 Human identity, Agent ownership/role grants, read-only control API, and
  same-origin product website with revocable short-lived browser sessions and
  organization-scoped visibility

## Verified local environment

| Capability | Status | Evidence / boundary |
| --- | --- | --- |
| Git | available | Git 2.50.1; repository initialized on 2026-08-12 |
| Python | available | bundled Python 3.12.13 |
| `uv` | available | `/Users/mars113/.local/bin/uv` |
| Node.js | partially available | bundled Node 24.14.0; below OpenClaw's declared Node 24 minimum of 24.15.0 |
| npm / OpenClaw host | unavailable | plugin host build/validate cannot run in this environment |
| Docker / Docker Compose | unavailable | command is not installed in the current host environment |
| PostgreSQL server/client | unavailable | no local `postgres` or `psql` command discovered |

Docker Compose and PostgreSQL assets are implemented. Fast tests run against the
same repository interfaces using SQLite, while a separately marked PostgreSQL
integration suite remains the authoritative persistence check.
Until it has run on a machine with Docker/PostgreSQL, that acceptance item remains
**not locally verified** and must not be reported as production acceptance.

## Milestone ledger

| Milestone | Scope | Status |
| --- | --- | --- |
| 0 | repository audit, status, architecture, plan | complete |
| 1 | FastAPI, PostgreSQL, Compose, health/readiness, Alembic, basic tests | complete* |
| 2 | Agent identity, registration, API keys, authentication, lookup | complete |
| 3 | persistent message/inbox APIs and offline delivery | complete |
| 4 | message lifecycle, explicit read and acknowledgement | complete |
| 5 | replies and thread history | complete |
| 6 | attachment upload/download, integrity and authorization | complete |
| 7 | address/capability directory | complete |
| 8 | inbound allow/block policy | complete |
| 9 | Python SDK | complete |
| 10 | offline/restart E2E, concurrency, security, and demo | complete* |
| 11 | OpenClaw integration | complete* |
| 12 | MCP adapter | complete |
| 13 | A2A compatibility mapping and low-risk adapter surface | complete* |
| 14 | 星云驿 naming and 星轨 read-only Human control plane | complete* |
| 15 | 星轨 short-lived browser sessions and server-side revocation | complete* |
| 16 | 星轨 organizations, memberships, and organization-scoped Agent visibility | complete* |

## Decisions already fixed

1. The server stores messages; agents need not be simultaneously online.
2. PostgreSQL, not realtime connections or a queue, is the durable source of truth.
3. Local delivery is atomic with inbox persistence. The API returns an acceptance
   receipt; a committed local message is already `delivered`, never merely held in
   volatile memory.
4. `read` and `ack` are explicit commands. `GET` never changes message state.
5. Authentication determines the sender. A request cannot choose an arbitrary
   `sender_agent_id`.
6. Messages and attachments are untrusted external inputs. Adapters must preserve
   that trust label and must not elevate message content into system instructions.
7. Idempotency is scoped to `(sender_agent_id, idempotency_key)` and payload
   mismatch on key reuse is a conflict.
8. OpenClaw, MCP, A2A, realtime transports, and future federation remain adapters;
   none is a core runtime dependency.
9. 星轨 Human identity is separate from Agent and Admin credentials. Human views
   are authorization-scoped, and `ACK` never means a task completed.
10. An organization is a server-side authorization scope, not a UI filter. One
    Agent can belong to one organization in the current model; direct grants and
    organization-derived visibility remain independent.

## 星轨 read-only control-plane evidence

The first Human control-plane slice is implemented at `/orbit` and
`/api/v1/orbit`. Admin-only bootstrap APIs create a Human identity, return a
one-time `hum_` key, and grant/revoke owner, operator, viewer, or auditor access to
an Agent. PostgreSQL models enforce one owner per Agent and explicit collaborator
grants. Human keys use a separate HMAC pepper.

The browser now sends the `hum_` key only to create a random short-lived `hss_`
session, clears the key input, and continues with an HttpOnly, SameSite cookie.
Only the session HMAC digest is stored. Sessions have a configurable default
12-hour lifetime, use `Secure` in production, survive refresh, and are revoked
server-side on sign-out. Bearer Human keys remain available for programmatic
read-only clients.

Organizations, Human membership roles (`owner`, `admin`, `member`, `auditor`),
and single-organization Agent assignments are now durable server-side records.
Organization owners/admins project to read-only operator visibility, members to
viewer visibility, and auditors remain body-redacted. Direct ownership/grants are
merged without being overwritten, so membership removal revokes only derived
access. 星轨 renders these relationships in the new “组织星图” section.

Six integration tests prove branding/security headers and no browser key
persistence; Human/Agent credential separation; owner-only communication
visibility; unrelated Agent isolation; auditor body redaction; grant revocation;
session creation/digest storage/revocation/expiry; production Secure-cookie
behavior; and the critical distinction that an ACKed task remains `pending` until
an explicit `result` changes its work state. The 0007 migration passed upgrade,
schema check, downgrade to 0006, re-upgrade, and a second schema check against a
fresh database. Three organization integration tests additionally cover Admin
isolation, canonical and unique organization identities, the single-organization
Agent invariant, membership-derived visibility, auditor redaction, immediate
revocation, direct-grant preservation, and audit events. The 0008 migration also
passed upgrade, schema check, downgrade to 0007, re-upgrade, and a second check.
The full locally runnable regression now reports 238 passed and one expected
loopback-sandbox skip, plus four MCP package tests; Ruff check/format and the
dependency-free browser script syntax check also pass.

This is a locally verified read-only control-plane slice, not public Human login.
It has not been deployed to Alibaba Cloud or exercised against PostgreSQL. The
current public IP remains plaintext HTTP and must not receive Human credentials.
Trusted HTTPS, MFA, recovery, Human key rotation, approvals, CSRF protection for
future Human writes, and Human action audit are later gates. Basic membership
exists; delegated administration, invitations, membership history, SSO/domain
proof, and nested organization units do not.

## Final local acceptance snapshot

The final repository checks completed on 2026-08-12 with these results:

- `make lint`: Ruff lint and format checks passed across 119 Python files.
- default full suite: 224 passed and four environment skips. Three skips are the
  guarded PostgreSQL acceptance cases; the fourth is the loopback E2E inside the
  restricted sandbox.
- the loopback E2E was then run with local-port permission and passed; `make demo`
  also completed all 12 real-Uvicorn restart steps.
- the MCP adapter's package-local suite passed four tests; the combined MCP,
  OpenClaw, and observability contract selection passed 22 tests.
- the zero-dependency OpenClaw Node client harness passed all four tests.
- Alembic completed upgrade-to-head, schema check, downgrade-to-base,
  re-upgrade-to-head, and a second schema check against a fresh file database.
- a fresh offline sdist and wheel build passed. The wheel contains the server,
  Admin assets, Python SDK, and MCP adapter; direct wheel import smoke checks
  passed.
- README Bash blocks passed `bash -n`, both Python blocks compiled, the envelope
  JSON parsed, the lockfile resolved, and `git diff --check` passed.

This is **local verified**, not production accepted. Docker/PostgreSQL commands
and a supported OpenClaw host remain unavailable on this machine.

## Definition of Done audit

`[x]` means implemented and exercised locally; `[~]` means the implementation and
acceptance asset exist but the required external runtime was unavailable.

- [x] Alice and Bob have unique Agent identities and canonical addresses.
- [x] API-key authentication binds the sender and rejects forged identities.
- [x] Alice can send while Bob has no running client; Bob later retrieves unread
  mail, marks it read, ACKs it, and replies.
- [x] Alice sees Bob's ACK projection, and both participants can retrieve complete
  thread history.
- [x] Attachments, capability Directory, inbound ACLs, and sender-scoped
  idempotency work through the API and automated tests.
- [x] The Python SDK supports send, Inbox, get/read/ACK/reply, Directory, and
  attachment operations.
- [x] The OpenClaw adapter implements basic send/inbox/read/reply/ACK/search over
  the public protocol; static and Node harness tests pass.
- [x] The optional MCP adapter exposes the corresponding six stdio tools.
- [x] `README.md`, `ARCHITECTURE.md`, `PROTOCOL.md`, `SECURITY.md`, Roadmap, ADRs,
  JSON Schema, deterministic examples, and `make demo` are present and verified.
- [~] PostgreSQL durability, restart, idempotency, row-lock, and 100-Agent tests
  are implemented in `tests/postgres` but not executed here because neither
  Docker nor PostgreSQL is installed.
- [~] Docker Compose one-command API/PostgreSQL startup and persistent volumes are
  implemented but not executed on this host.
- [~] All locally runnable automated tests pass; the three PostgreSQL cases must
  pass with zero skips before a production-database acceptance claim.

## Milestone evidence trail

`*` Milestone 1 fast-test evidence: 7 tests passed, Ruff passed, and the Alembic
baseline ran through the SQLite adapter. Docker Compose and PostgreSQL execution
remain not locally verified because this host has neither command installed.

Milestone 3 evidence: 60 fast tests passed, including application recreation on a
file-backed database, sender forgery rejection, sender-scoped idempotency,
participant isolation, cursor integrity, equal-timestamp pagination, and explicit
`external_agent_content` labelling. Real PostgreSQL restart remains a later marked
acceptance target.

Milestone 6 evidence: 133 fast tests passed. The 15 attachment-specific security
tests cover actual-byte limits, SHA256, unsafe filenames, temporary-file cleanup,
single-use sender-owned binding, participant-only download, atomic rollback,
task/result attachments, and persistence across complete application recreation.
Alembic upgrade/check/downgrade/upgrade passed against SQLite; PostgreSQL execution
remains explicitly unverified on this host.

Milestone 8 evidence: 151 fast tests passed, including 18 independent ACL tests.
The suite covers public/allowlist/contacts-only/private policies, canonical Agent
and domain rules, block precedence, send/reply re-authorization, historical mail
visibility, idempotent replay after a policy change, denial rollback, and audit
records. SQLite migration round-trips pass; PostgreSQL row-lock concurrency remains
explicitly unverified on this host.

Milestone 9 evidence: 29 SDK contract tests passed using HTTP mock transports.
The single distribution exposes `from agentpost import AgentPost`, while the SDK
implementation depends only on public HTTP/JSON protocol types. Offline sdist and
wheel builds, isolated wheel installation, deterministic example compilation, and
all example `--help` smoke checks passed.

Milestone 10 evidence: the real-process `make demo` completed all 12 Alice/Bob
steps, including terminating Uvicorn and restarting it against the same durable
database. Fast acceptance covers two application restarts with task/result
attachments, 100 concurrent Agents without lost delivery, 32-way idempotency,
concurrent read/ACK, authorization isolation, forged state, malformed JSON, and
log-secret canaries. The PostgreSQL suite and isolated Compose manifest exist and
collect safely, but their three tests are **not locally executed** because this
host has no Docker or PostgreSQL command. That remaining boundary is why the
milestone carries an asterisk rather than a production acceptance claim.

Milestone 11 evidence: the TypeScript ESM native tool plugin exposes exactly six
strict TypeBox tools and imports only the OpenClaw tool-plugin SDK plus the public
AgentPost HTTP protocol. Seven independent contract/security checks and four
zero-dependency Node client tests pass; the full fast suite reports 200 passed and
four environment skips. The adapter fixes the server URL and credential in admin
configuration, propagates cancellation and idempotency keys, performs no hidden
retry, preserves `external_agent_content`, and sanitizes errors. A real
`openclaw plugins build/validate` remains **not locally executed** because npm,
OpenClaw, and TypeBox are unavailable and the bundled Node 24.14.0 is outside the
plugin's declared supported ranges; this is why the milestone carries an asterisk
rather than a host-compatibility acceptance claim.

Milestone 12 evidence: the optional `agentpost_mcp` package is locked to the
official Python MCP SDK 2.0.0 and exposes exactly six stdio tools over the public
Python SDK. Thirteen adapter tests pass, including a real in-process MCP Client;
a real stdio subprocess lists all six tools without protocol noise. The wheel and
sdist include the adapter and `agentpost-mcp` entry point. Calls use an independent
SDK client, preserve opaque cursors and explicit idempotency keys, perform no
hidden retry, and return sanitized structured errors. Inbox, message, and
directory results are labeled `external_agent_content`; server-internal forward-
compatible fields are filtered without interpreting or rewriting opaque business
content. The full fast suite reports 210 passed and four expected environment
skips.

Milestone 13 evidence: `docs/A2A_MAPPING.md` defines a normative A2A 1.0
compatibility boundary and a machine-readable contract registry; six contract
tests pass. The mapping keeps mailbox Delivery and A2A Task state permanently
separate (`ACK` has no Task effect), requires restart-safe principal-scoped task
bindings, preserves Inbox durability, treats Cards/Parts/Artifacts as untrusted,
and forbids advertising streaming, push, cancellation, or verified skills before
implementation. `integrations/a2a/` is intentionally only a reserved adapter
surface: no A2A runtime endpoint or conformance claim is shipped, which is why
the milestone carries an asterisk.

Admin/debug evidence: an optional `/admin` console and five read-only operational
endpoints are hidden unless a 32–512 character Admin token is configured. Four
integration tests cover disabled/wrong-token generic 404 behavior, safe Agent,
Message, Thread, Delivery, and Audit projections, absence of body/key/storage
secrets, and security headers. The console creates test Agents through the
existing registration boundary, reads an Agent Inbox, and sends idempotent test
messages; credentials stay in password inputs/page memory and external data is
rendered only as text. A real wheel build includes all HTML/CSS/JS assets.

## Alibaba Cloud deployment evidence

On 2026-08-13, the committed service was installed on a dedicated Alibaba Cloud
Light Application Server in Hangzhou. A provider snapshot named
`agentpost-baseline-20260813` was completed before mutation. The active origin
uses Ubuntu 24.04, PostgreSQL 16, a Python 3.12 virtual environment, systemd,
Nginx, a private filesystem attachment directory, and server-only generated
production secrets. AgentPost, Nginx, and PostgreSQL all reported `active` after
deployment, and `/health` and `/ready` passed both on the origin and through the
server's public HTTP endpoint.

The first PostgreSQL send exposed an ORM flush-order defect that SQLite's default
foreign-key behavior had hidden. The transaction rolled back cleanly. Commit
`01c97a1` stages the durable message and delivery before the sender-scoped
idempotency record, retains a single database transaction, and adds a regression
test with immediate foreign-key enforcement. The resulting local suite passed
227 tests with one environment-only loopback skip and three PostgreSQL cases
deselected.

The cloud acceptance then passed against real PostgreSQL: Alice sent while no Bob
client was running; the delivery was persisted; the AgentPost service restarted;
Bob found the unread message, marked it read, ACKed it, and replied; Alice found
the reply; and the thread contained exactly two messages. This establishes
`deployed_origin_verified`, not full public production acceptance.

`agentpost.me` DNS, ICP filing, and HTTPS were intentionally not changed. Until
the registration review and user-controlled filing/DNS steps complete, the
branded public endpoint remains pending. Operational paths, verification, and
rollback are recorded in `docs/ALIYUN_DEPLOYMENT.md`.

## Immediate next action

After the domain registration review completes, the user-controlled next gate is
ICP filing for the Hangzhou origin. Only after filing should DNS be pointed to the
server and HTTPS be issued and verified. Separately run the OpenClaw plugin's
build/load/validate commands in a supported host before claiming host
compatibility. Production hardening and later phases remain governed by
`SECURITY.md` and `ROADMAP.md`.
