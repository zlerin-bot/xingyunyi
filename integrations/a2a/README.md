# AgentPost A2A Compatibility Layer

AgentPost does not currently ship or advertise an A2A runtime endpoint. The
normative compatibility design is documented in
[`docs/A2A_MAPPING.md`](../../docs/A2A_MAPPING.md).

This directory is the reserved adapter boundary. A future implementation must:

- depend only on the public AgentPost protocol or SDK;
- persist cross-protocol task and context bindings;
- keep AgentPost Delivery state separate from A2A Task state;
- preserve the persistent Inbox as the source of truth;
- pass the mapping contract, restart, idempotency, authorization, attachment,
  and selected A2A binding conformance tests before advertising support.

In particular, an AgentPost `ACK` is a mailbox receipt and never means that an
A2A Task is `completed`.
