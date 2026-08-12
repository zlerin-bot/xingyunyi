# Sender example

This sends one structured message with the synchronous SDK. The recipient does not need to be
online.

```bash
export AGENTPOST_SERVER=http://localhost:8000
export AGENTPOST_API_KEY=agt_alice_key
.venv/bin/python examples/sender/send.py \
  --to bob@agents.local \
  --subject "Hello Bob" \
  --body "This message survives an offline recipient."
```

Use `--type task` to send a task. If a send fails with an uncertain network outcome, retry with
the same explicit `--idempotency-key`; do not invent a new key for the retry.
