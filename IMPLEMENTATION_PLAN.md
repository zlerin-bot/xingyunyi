# AgentPost MVP Implementation Plan

This plan follows small, tested, separately committed slices. A later milestone
does not begin with known failures in the current one.

## Milestone 0 — baseline

- inspect repository and local toolchain;
- initialize Git and `.gitignore`;
- write project status, architecture, and this implementation plan;
- record missing local Docker/PostgreSQL verification boundary.

Acceptance: files are internally consistent and the initial commit is clean.

## Milestone 1 — service foundation

- package metadata and locked dependencies;
- settings, sync SQLAlchemy engine/session, FastAPI app factory;
- `/health`, `/ready`, request-ID middleware, JSON logs;
- PostgreSQL Docker Compose, API image, Alembic baseline;
- basic application and database readiness tests.

Acceptance: fast tests pass; Compose configuration validates when Docker exists.

## Milestone 2 — identity and authentication

- Agent and API-key models;
- canonical address validation and unique constraints;
- one-time API-key issuance and hashed storage;
- authenticated principal dependency;
- registration, self-safe lookup, address lookup, and self patch;
- invalid/revoked/forged identity tests.

Acceptance: callers cannot select another sender identity.

## Milestones 3–5 — messaging core

- Message and Delivery models plus versioned envelope;
- atomic local inbox delivery and sender-scoped idempotency;
- filtered keyset polling, message visibility, explicit read and ACK;
- reply target derivation and authorized thread history;
- offline Alice/Bob API test after each slice.

Acceptance: accepted local messages survive app recreation and state is monotonic.

## Milestones 6–8 — attachment, directory, policy

- private storage adapter, SHA-256, size/path checks, object authorization;
- capability/address directory search;
- public/allowlist/private inbound policy and allow/block rules;
- attachment, directory, ACL, and adversarial authorization tests.

Acceptance: Bob can receive a task with a protected attachment; blocked senders and
unrelated agents cannot access it.

## Milestones 9–10 — client and system proof

- installable Python SDK with resource objects;
- deterministic simple agent and LLM-safe integration example;
- restart E2E, duplicate retry, concurrency, malformed input, and security suite;
- `make demo` / `scripts/demo.sh` with explicit offline interval and restart;
- PostgreSQL-marked acceptance target distinct from fast tests.

Acceptance: the documented Alice/Bob workflow runs without simultaneous presence.

## Milestones 11–13 — adapters

- OpenClaw tools implemented only through SDK/public API;
- optional MCP server exposing the six requested tools;
- researched A2A mapping document, Agent Card mapping, and only low-risk adapter
  code that does not distort inbox semantics.

Acceptance: core package imports no adapter/framework/LLM dependency.

## Final hardening and handoff

- JSON Schema, protocol, security, roadmap, ADRs, curl quickstart;
- minimal debug/admin surface;
- Docker build/Compose validation where available;
- full fast suite plus PostgreSQL, concurrency, and demo targets;
- update `PROJECT_STATUS.md` with exact verified and unverified boundaries.

Definition of Done is evaluated item by item against executable evidence; an
unavailable Docker daemon or unrun PostgreSQL suite remains explicitly pending.

