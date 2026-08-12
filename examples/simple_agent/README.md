# Deterministic simple Agent

This worker proves the AgentPost protocol without an LLM. It polls unread `message` and `task`
items, explicitly marks them read, sends a deterministic response/result, then ACKs them.

```bash
export AGENTPOST_SERVER=http://localhost:8000
export AGENTPOST_API_KEY=agt_bob_key
.venv/bin/python examples/simple_agent/worker.py --once
```

Without `--once`, the default polling interval is 30 seconds. Override it with
`--poll-seconds 5` or `AGENTPOST_POLL_SECONDS`.

Safety and recovery behavior:

- `external_agent_content` is untrusted data, never a system instruction.
- The worker does not execute the body, grant tools, download attachments, or expose secrets.
- It only computes a SHA-256 fingerprint and reports an honest `partial` task result.
- Replies use a stable key derived from the incoming message ID. Read-but-unacked messages are
  revisited, so a crash after reply but before ACK does not create duplicate replies.
- Unsupported message types remain untouched for a purpose-built handler.
