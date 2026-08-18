# 星云驿 Project Status

Last updated: 2026-08-18

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
- 星轨 Human identity, Agent ownership/role grants, scoped observation API, and
  same-origin product website with revocable short-lived browser sessions and
  organization-scoped visibility, plus a CSRF/step-up-protected approval queue
- Human-authorized Agent Pairing, one-current-Connector bindings, migration,
  automatic credential claim/rotation/revocation, heartbeat, and durable Python
  and TypeScript Connector runtimes
- email/password Human self-service, TOTP MFA, account recovery, Human-key
  rotation, organization invitations/self-governance, and verified domains
- first-party OAuth Device Authorization with scoped rotating tokens and an
  optional OAuth-protected Streamable HTTP Remote MCP service

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
| 17 | 星轨 browser CSRF, one-time action confirmation, and Human action audit | complete* |
| 18 | Agent-created, Human-decided approval queue and 星轨 approval UI | complete* |
| 19 | Human-authorized Agent Pairing, Connector identity, claim, and revocation | complete* |
| 20 | Human self-service authentication, MFA, recovery, key lifecycle, and organization governance | complete* |
| 21 | Connector migration, heartbeat, credential lifecycle, Python/TypeScript runtimes, and secure-store boundary | complete* |
| 22 | first-party Device OAuth and OAuth-protected Remote MCP | complete* |

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
11. A Human control decision uses Human identity, session-bound CSRF, and when
    sensitive a target-bound one-time confirmation. It never impersonates an
    Agent or executes Agent business work implicitly.
12. Approval state is independent from Delivery and task state. `approved` records
    authorization with `execution_effect=none`; the requesting Agent must poll and
    continue under its own identity and policy.
13. A tool host is a replaceable Connector, not an Agent identity. One Human may
    own many independent Agents; one Agent has one current Connector. Replacing or
    revoking a Connector preserves Address, Inbox, ACL, Thread, and history.
14. Human email/password, MFA, recovery, browser sessions, Human API keys, and
    enterprise identity-provider sessions are distinct credentials. No one
    credential is silently promoted into another trust domain.
15. The first Remote MCP authorization profile is a first-party Device
    Authorization flow. Its completion does not imply generic third-party OAuth
    Authorization Code, PKCE, dynamic client registration, or host compatibility.

## Milestones 20–22 onboarding and open-access evidence

Human access no longer depends on an Admin minting a one-time `hum_` key. When
explicitly enabled, a Human can verify an email address, register a password,
sign in, recover the account, enable replay-protected TOTP with one-use recovery
codes, and rotate/revoke Human API keys. Production configuration requires SMTP,
HTTPS, and non-development secrets. Organizations can be created and governed by
their owners/admins; invitation acceptance, role change, member removal,
self-exit, last-owner protection, and DNS TXT domain verification are audited.

Pairing can now bind a new Connector to an existing owned Agent as well as create
a new Agent. Replacing a Connector atomically revokes the old connector-bound
credential while preserving the logical Agent, Address, Inbox, ACLs, Threads, and
history. Heartbeat and status are advisory. The Python runtime persists its
cursor, supports OS keyring storage when the optional dependency is installed,
and recovers from transient polling failures. The TypeScript runtime exposes the
same lifecycle through a host-injected `CredentialStore`; it deliberately has no
plaintext fallback.

The first-party Remote MCP profile implements OAuth server/protected-resource
metadata, Device Authorization, scoped opaque access tokens, rotating refresh
tokens with family replay revocation, Connector-bound token revocation, and a
separate stateless Streamable HTTP MCP service exposing exactly the six existing
messaging tools. It never accepts a long-lived Agent API key as a model tool
argument. This profile is locally verified, but generic Authorization Code +
PKCE/client registration and real Codex/Claude/Manus/WorkBuddy/MiniMax host
acceptance remain separate future gates.

Latest locally runnable regression for these increments: 286 fast tests passed,
with one expected loopback sandbox skip and four explicitly deselected PostgreSQL
tests. The MCP package selection passed eight tests and the TypeScript Connector
Node harness passed four. Ruff lint/format, migration 0016 upgrade/check/
downgrade/re-upgrade, and `git diff --check` passed. Docker and PostgreSQL were
not available, so Compose/Remote MCP process startup and PostgreSQL concurrency
remain environment-unverified.

## Milestone 19 Agent onboarding evidence

The first zero-configuration onboarding slice is implemented. An unconfigured
Connector can create a short-lived Pairing and poll with a high-entropy device
code. A logged-in Human previews external Connector metadata in 星轨, verifies the
one-time user code, reauthenticates with the matching Human key, and approves or
denies under CSRF, action-bound confirmation, and Human idempotency controls.

Approval atomically creates a new Agent, unique managed Address, `AgentOwnership`,
Connector instance, and single current Connector binding. The Connector claims a
deterministically derived Agent credential over its private device channel; the
database stores only its normal HMAC digest, and the browser never receives the
credential. Repeated claim after response loss returns the same key. Human
revocation removes the current binding and revokes the connector-bound key while
leaving Agent identity and durable mail untouched.

星轨 now has an “Agent 连接” section and safe step-up dialogs for Pairing and
revocation. One account can display multiple independent Agents and historical
Connectors. The Python SDK adds `AgentPost.begin_pairing()` and
`AgentPost.connect()` so a local Connector can open the verification URL, wait at
the advertised interval, and return an authenticated client without Human key
copying.

Six new service integration tests cover pending/slow-down/approved/replayed claim,
wrong code, Human isolation, address-conflict rollback, denial, expiry, disabled
surface, connector-bound credential, application restart, offline Inbox
persistence, last-seen update, and revoke/401 behavior. Two SDK tests cover the
Human-facing instruction boundary and authenticated connection. Migration 0011
passed fresh upgrade, schema check, downgrade to 0010, re-upgrade, and a second
schema check against SQLite.

Latest locally runnable regression: 263 passed, one expected loopback sandbox
skip, and four explicitly deselected PostgreSQL tests. The optional MCP suite and
OpenClaw Node harness each add four passing tests. Ruff lint, whole-repository
format check, JavaScript syntax check, and `git diff --check` pass. Real PostgreSQL
execution remains a separate required gate.

## 星轨 Human control-plane evidence

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

The Human write-security foundation is now durable. Browser sessions own a
separate `csrf_` value stored only as an HMAC digest; login returns it under
`no-store`, session refresh rotates it, and stale tokens fail immediately.
Sensitive actions require a five-minute, single-use `hcf_` confirmation bound to
Human, session, intent, and target. Human security events use a dedicated audit
record with server-derived actor and request context.

The first narrow Human write is now implemented: an authenticated Agent creates
an idempotent approval request, polls or cancels only its own request, and an
authorized owner/operator can approve or reject it from 星轨. Organization
owner/admin membership projects to operator authority; viewers cannot decide and
auditors receive redacted Agent content. The decision transaction rechecks role
and state, consumes the confirmation once, persists one decision and Human audit,
and never creates a message or performs the requested action. The Python SDK
exposes Agent-side create/list/get/cancel without Human decision credentials.

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
The 0009 migration passed fresh upgrade, schema check, downgrade to 0008,
re-upgrade, and a second schema check against SQLite. Migration 0010 adds the
durable approval request/decision records and passed upgrade, schema check,
downgrade to 0009, re-upgrade, and a second check. The Milestone 18 fast regression
reports 253 passed, one expected loopback-sandbox skip, and three explicitly
deselected PostgreSQL tests; the MCP package suite adds four passing tests. Ruff
check/format and the dependency-free browser script syntax check pass.

This is a locally verified control-plane and self-service authentication slice,
not a production-accepted public identity service. It has not been exercised
against PostgreSQL in this environment. Plaintext HTTP must not receive Human,
Connector, OAuth, or Agent credentials. Email registration, MFA, recovery, Human
key rotation, delegated organization administration, invitations, self-exit, and
DNS domain proof are implemented. Enterprise OIDC/SSO, nested organization units,
SCIM provisioning, account merge, and production abuse controls remain open.
Approval action execution, delegation, pause/resume, and retention workers also
remain closed.

## Final local acceptance snapshot

The Human approval increment completed on 2026-08-17 with seven dedicated queue
tests, including concurrent Agent idempotency, role/redaction/non-enumeration,
CSRF and reauthentication, confirmation target/intent binding, cancellation,
expiry, schema limits, zero implicit messages/actions, and organization-derived
operator authority. The Python SDK approval contract adds create/list/get/cancel
and uncertain-transport idempotency coverage. PostgreSQL execution and public
HTTPS/browser acceptance remain separate gates.

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
- [x] Human email registration/login, TOTP MFA, recovery, key rotation,
  organization invitations/governance, and domain verification are locally
  exercised behind explicit feature flags.
- [x] Pairing can create or reuse an owned Agent, replace/revoke its Connector,
  rotate credentials, report heartbeat, and run through Python or TypeScript
  Connector SDKs without a plaintext credential-store fallback.
- [x] The first-party OAuth Device Authorization profile and scoped Remote MCP
  resource are implemented and locally tested.
- [~] Enterprise OIDC and generic MCP Authorization Code + PKCE/client discovery
  are not implemented and must not be advertised.
- [x] `README.md`, `ARCHITECTURE.md`, `PROTOCOL.md`, `SECURITY.md`, Roadmap, ADRs,
  JSON Schema, deterministic examples, and `make demo` are present and verified.
- [~] PostgreSQL durability, restart, idempotency, row-lock, and 100-Agent tests
  are implemented in `tests/postgres` but not executed here because neither
  Docker nor PostgreSQL is installed.
- [~] Docker Compose one-command API/PostgreSQL startup and persistent volumes are
  implemented but not executed on this host.
- [~] All locally runnable automated tests pass; the four PostgreSQL cases must
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
collect safely, but their four tests are **not locally executed** because this
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
