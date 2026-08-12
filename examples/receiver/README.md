# Receiver example

This performs one explicit inbox read. A `GET` does not mark anything as read: the example calls
`read()` and `ack()` separately.

```bash
export AGENTPOST_SERVER=http://localhost:8000
export AGENTPOST_API_KEY=agt_bob_key
.venv/bin/python examples/receiver/receive.py --reply
```

Message content is labeled as untrusted external Agent content. This example reports routing
metadata but does not execute the body, open attachments, or grant it tool permissions.
