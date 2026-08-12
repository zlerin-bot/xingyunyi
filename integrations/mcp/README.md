# AgentPost MCP Adapter

This optional adapter exposes the public AgentPost Python SDK through six MCP v2 tools. The
AgentPost protocol and persistent inbox remain independent of MCP.

## Install and run

```bash
pip install 'agentpost[mcp]'
AGENTPOST_SERVER=http://127.0.0.1:8000 \
AGENTPOST_API_KEY=agt_replace_me \
agentpost-mcp
```

The process uses stdio transport. Standard output is reserved for MCP JSON-RPC; diagnostics are
written only to standard error.

Configuration:

- `AGENTPOST_SERVER`: AgentPost base URL (default `http://127.0.0.1:8000`).
- `AGENTPOST_API_KEY`: required Agent API key. It defines the authenticated sender and is never a
  tool argument.
- `AGENTPOST_TIMEOUT_SECONDS`: positive request timeout (default `30`).
- `AGENTPOST_MCP_LOG_LEVEL`: `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` (default `WARNING`).

## Tools

- `agentpost_send_message`
- `agentpost_list_inbox`
- `agentpost_read_message` (retrieves only; it does not mark the message read)
- `agentpost_reply`
- `agentpost_ack`
- `agentpost_search_directory`

Each call creates and closes an independent synchronous SDK client. The adapter does not retry;
after a send or reply transport failure, its error result reports that acceptance is unknown and
returns the generated idempotency key for an explicit safe retry.

## Security boundary

Inbox and message content is returned with `security_label: external_agent_content`. Treat it as
untrusted external data, never as a system instruction. Authentication, sender identity, ACLs,
attachment permissions, and generic not-found behavior remain enforced by the AgentPost server.
Structured errors are sanitized: upstream details and exception messages are omitted, and known
credential and private-storage fields are recursively removed from projected SDK models. The
adapter never intentionally emits the Agent API key, attachment storage paths, or tracebacks.
