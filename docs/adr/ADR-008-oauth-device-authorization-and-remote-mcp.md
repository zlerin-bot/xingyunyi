# ADR-008: First-party Device OAuth for Remote MCP

- Status: accepted
- Date: 2026-08-18

## Context

Cloud-hosted Agent tools cannot safely receive a long-lived `agt_` credential in
a model-visible tool argument. They also cannot depend on an inbound connection to
the user's laptop. AgentPost already has Human-authorized Pairing, persistent
Inbox semantics, and Connector identity, so Remote MCP needs an authorization
profile that reuses those trust boundaries without making MCP the identity source.

## Decision

The first Remote MCP profile uses OAuth Device Authorization for one fixed
first-party client, `agentpost-remote-mcp`.

- The device flow creates an OAuth-mode Pairing and reuses the existing 星轨 Human
  review, ownership check, reauthentication, confirmation, and audit transaction.
- Access and refresh tokens are opaque, Connector-bound values. Only HMAC digests
  are stored. Access tokens carry the single `agentpost.messaging` scope and a
  fixed Remote MCP resource audience.
- Refresh tokens rotate on every use. Reuse of an already rotated token revokes
  the token family.
- Connector replacement or revocation revokes every token family issued to that
  Connector.
- The API enforces an explicit method/path allowlist for the messaging scope. An
  OAuth token cannot call Human, Admin, Pairing-management, attachment-upload, or
  unrelated Agent-management endpoints.
- Remote MCP runs as a separate stateless Streamable HTTP adapter. It validates
  the presented access token through a protected token-info endpoint and then
  calls the public AgentPost protocol using that same short-lived token.
- PostgreSQL remains the message and authorization source of truth. MCP sessions,
  realtime connectivity, and OAuth transport state do not replace the Inbox.

## Alternatives rejected

- Passing a long-lived Agent API key as an MCP tool parameter exposes durable
  identity material to prompts, tool traces, and host logs.
- Treating an MCP transport session as an Agent identity loses offline and restart
  semantics and couples the core to one integration protocol.
- Claiming universal OAuth support from Device Authorization alone is misleading.
  Many hosted clients require Authorization Code + PKCE and client metadata or
  registration profiles.

## Consequences

The first-party Remote MCP service can authorize an Agent without manual API-key
copying and can safely survive Connector migration and refresh-token replay. The
scope is intentionally narrow.

This ADR does **not** claim support for generic OAuth Authorization Code + PKCE,
dynamic client registration, CIMD, enterprise OIDC, or any named third-party
host. Each additional profile needs its own threat model, implementation, and
real-host acceptance evidence before it is advertised.
