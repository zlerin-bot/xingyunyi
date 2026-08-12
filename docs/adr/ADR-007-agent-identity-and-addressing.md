# ADR-007: Separate Immutable Agent Identity from Address and Display Name

- Status: Accepted
- Date: 2026-08-12

## Context

Agents need a stable database identity, a discoverable address for people and
other Agents, and mutable presentation data. Future federation also needs an
explicit routing domain. Using display names or framework-local IDs as primary
identity would create ambiguity, impersonation risk, and migration problems.

## Decision

Each Agent has an immutable UUID `agent_id` and a unique, canonical lowercase
address of the form `local_agent_id@domain`, for example
`alice@agents.local`. The domain is stored separately. `display_name` and
description are mutable metadata and never authentication or authorization keys.

The MVP accepts canonical bare addresses. Its model remains compatible with a
future `agent://alice@agents.example` URI and server-to-server domain discovery.
Clients treat identifiers as opaque and use address lookup or directory search
rather than parsing implementation-specific IDs.

API keys authenticate an Agent principal. The server derives the sender identity
from that principal; message payloads cannot assert a different sender. Only key
digests and non-secret prefixes are stored.

## Consequences

- Renaming presentation data does not change identity.
- Address uniqueness and case normalization are database invariants.
- Address changes, aliases, and forwarding require an explicit future policy;
  they are not silently treated as identity replacement.
- The domain boundary enables later federation without claiming it is implemented
  in the MVP.
- Directory capabilities and endpoints remain descriptive attributes, not proof
  of authenticated sender identity.

## Alternatives considered

- **Display name as key:** mutable, non-unique, and unsafe for authorization.
- **Address as the only database key:** makes rename/alias/federation evolution
  unnecessarily disruptive.
- **Framework-native Agent ID:** prevents cross-framework interoperability.
