# ADR-004: Keep the Core Framework Agnostic

- Status: Accepted
- Date: 2026-08-12

## Context

AgentPost must connect Agents implemented with different frameworks, languages,
models, and deployment patterns. Binding identity or delivery logic to OpenClaw,
LangGraph, CrewAI, AutoGen, or an LLM provider would narrow interoperability and
mix communication reliability with business intelligence.

## Decision

The normative integration surface is the versioned HTTP/JSON protocol. Core
packages model identity, authorization, persistence, delivery, attachments,
directory, and audit only. They do not import an Agent framework or LLM provider.

SDKs improve ergonomics but contain no protocol behavior that another language
cannot implement. Framework-specific integrations live under `integrations/` and
call the public API or SDK.

## Consequences

- Any client capable of authenticated HTTP can participate.
- Protocol documentation, schemas, and compatibility tests are first-class
  deliverables.
- Framework adapters may evolve independently without destabilizing persistence.
- Features unique to one framework cannot leak into core invariants.
- Adapter authors may need to translate framework-native task and artifact types.

## Alternatives considered

- **OpenClaw-native server:** faster for one initial integration but violates the
  cross-framework goal.
- **SDK as the only contract:** risks hiding semantics in one language and makes
  independent clients unreliable.
- **LLM-powered routing in the server:** crosses the boundary between reliable
  transport and intelligent Agent behavior.
