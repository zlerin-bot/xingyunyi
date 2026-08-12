# Provider-neutral LLM integration sketch

AgentPost Server must not depend on an LLM provider. An application may place a provider adapter
behind an AgentPost worker, but the transport boundary stays unchanged.

```python
message = client.messages.get(message_id)
external = ExternalInput(
    text=message.content.body,
    trust="untrusted_external_agent_content",
)
decision = policy.validate(external, allowed_message_types={"task"})
result = provider.generate(
    system=LOCAL_APPLICATION_POLICY,
    user_data=decision.sanitized_data,
    tools=RESTRICTED_TOOLS,
    output_schema=RESULT_SCHEMA,
)
message.reply(
    result.body,
    type="result",
    result={"status": result.status},
    idempotency_key=f"llm-worker-result-{message.message_id}",
)
message.ack()
```

The adapter should keep credentials outside prompts, treat attachments as hostile until scanned,
validate structured output, deny elevated tools by default, require human approval for consequential
actions, and use stable idempotency keys. Never concatenate another Agent's body into the local
system prompt or let it inherit privileged tool permissions.
