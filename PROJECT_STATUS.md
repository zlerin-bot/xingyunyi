# AgentPost Project Status

Last updated: 2026-08-12

## Current state

This repository started as an empty directory. There was no existing application,
package manifest, test suite, database model, or Git history to reuse.

The project is being built as a protocol-first modular monolith:

- FastAPI HTTP service
- SQLAlchemy 2.x persistence layer
- PostgreSQL as the production source of truth
- Alembic migrations
- local filesystem attachment adapter with an S3-compatible boundary
- framework-neutral REST/JSON protocol
- Python SDK plus optional OpenClaw, MCP, and A2A adapters

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

Docker Compose and PostgreSQL assets will still be implemented. Fast tests will
run against the same repository interfaces using SQLite, while a separately
marked PostgreSQL integration suite will be the authoritative persistence check.
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
| 13 | A2A compatibility mapping and low-risk adapter surface | pending |

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

## Immediate next action

Document Milestone 13 A2A compatibility mapping and add only a low-risk adapter surface.

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

Milestone 9 evidence: 26 SDK contract tests passed using HTTP mock transports.
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
OpenClaw, and TypeBox are unavailable and the bundled Node 24.14.0 is below the
plugin's declared Node 24.15.0 minimum; this is why the milestone carries an
asterisk rather than a host-compatibility acceptance claim.

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
