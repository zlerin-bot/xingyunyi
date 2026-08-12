# ADR-005: A2A and MCP Are Adapters, Not Core Dependencies

- Status: Accepted
- Date: 2026-08-12

## Context

MCP provides a useful tool-call entry point, while open Agent-to-Agent protocols
provide discovery, Agent Card, task, message, and artifact concepts. AgentPost has
a separate primary concern: an offline, persistent inbox with explicit delivery
and acknowledgement semantics. Replacing that core with either adapter would
couple durability to an external protocol lifecycle.

## Decision

MCP and A2A compatibility live under `integrations/mcp/` and
`integrations/a2a/`. They translate external tool or protocol concepts to the
public AgentPost HTTP API or Python SDK. Core modules never import those adapters.

The MCP server exposes AgentPost operations as tools but does not become the
AgentPost wire protocol. Initial A2A work documents mappings among Agent Card,
Task, Message, Artifact and AgentPost Agent, capabilities, task/result messages,
attachments, directory, and inbox. The project will not fork or reimplement the
entire A2A ecosystem.

## Consequences

- MCP-capable and A2A-capable Agents can integrate without constraining other
  clients.
- AgentPost retains its offline mailbox and lifecycle semantics.
- Translation gaps and lossiness must be documented and tested in adapters.
- External protocol upgrades can be absorbed at the integration boundary.
- Adapter failure cannot redefine acceptance of a message already in AgentPost.

## Alternatives considered

- **Make MCP the native protocol:** MCP tool invocation does not itself define the
  durable cross-time mailbox contract.
- **Adopt A2A wholesale as persistence:** risks losing AgentPost's distinct inbox,
  offline, and explicit ACK semantics.
- **Duplicate external protocols in core:** increases drift and maintenance risk.
