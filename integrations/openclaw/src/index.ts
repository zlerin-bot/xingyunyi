import { defineToolPlugin } from "openclaw/plugin-sdk/tool-plugin";
import { Type } from "typebox";

import {
  AgentPostHttpClient,
  AgentPostHttpError,
  type AgentPostPluginConfig,
  safeToolError,
} from "./client.js";

const messageTypes = [
  "message",
  "task",
  "request",
  "response",
  "notification",
  "event",
  "error",
  "system",
] as const;
const replyMessageTypes = [...messageTypes, "result"] as const;
const priorities = ["low", "normal", "high", "urgent"] as const;
const formats = ["text", "markdown", "json"] as const;
const inboxStatuses = ["unread", "delivered", "read", "acked"] as const;

const strict = { additionalProperties: false } as const;
const idempotencyKey = Type.Optional(
  Type.String({
    minLength: 1,
    maxLength: 255,
    description: "Reuse this exact value when explicitly retrying an uncertain call.",
  }),
);
const attachmentIds = Type.Optional(
  Type.Array(Type.String({ format: "uuid" }), { maxItems: 32, uniqueItems: true }),
);
const resultSchema = Type.Object(
  {
    ok: Type.Literal(true),
    data: Type.Unknown(),
    security_label: Type.Literal("external_agent_content"),
    idempotency_key: Type.Optional(Type.String()),
  },
  strict,
);

const configSchema = Type.Object(
  {
    baseUrl: Type.String({ format: "uri", minLength: 8, maxLength: 2048 }),
    apiKey: Type.String({ minLength: 20, maxLength: 256 }),
    timeoutMs: Type.Optional(
      Type.Integer({ minimum: 100, maximum: 120_000, default: 30_000 }),
    ),
  },
  strict,
);

function api(config: AgentPostPluginConfig): AgentPostHttpClient {
  return new AgentPostHttpClient(config);
}

function generatedKey(): string {
  return `openclaw_${crypto.randomUUID()}`;
}

function result(data: unknown, key?: string) {
  return {
    ok: true as const,
    data,
    security_label: "external_agent_content" as const,
    ...(key ? { idempotency_key: key } : {}),
  };
}

export default defineToolPlugin({
  id: "agentpost-tools",
  name: "AgentPost Tools",
  description: "Thin OpenClaw tools for AgentPost's public asynchronous messaging API.",
  configSchema,
  tools: (tool) => [
    tool({
      name: "agentpost_send",
      label: "Send AgentPost message",
      description: "Send a durable message or task. The authenticated API key selects sender identity.",
      optional: true,
      parameters: Type.Object(
        {
          to: Type.String({ minLength: 3, maxLength: 320 }),
          subject: Type.String({ maxLength: 500 }),
          body: Type.Unknown({ description: "Untrusted external message content." }),
          type: Type.Optional(Type.Union(messageTypes.map((value) => Type.Literal(value)))),
          format: Type.Optional(Type.Union(formats.map((value) => Type.Literal(value)))),
          task: Type.Optional(Type.Record(Type.String(), Type.Unknown())),
          attachment_ids: attachmentIds,
          priority: Type.Optional(Type.Union(priorities.map((value) => Type.Literal(value)))),
          requires_ack: Type.Optional(Type.Boolean()),
          metadata: Type.Optional(Type.Record(Type.String(), Type.Unknown())),
          expires_at: Type.Optional(Type.String({ format: "date-time" })),
          idempotency_key: idempotencyKey,
        },
        strict,
      ),
      outputSchema: resultSchema,
      async execute(params, config, context) {
        const key = params.idempotency_key ?? generatedKey();
        try {
          const data = await api(config).request({
            method: "POST",
            path: "/messages",
            signal: context.signal,
            idempotencyKey: key,
            acceptanceUnknownOnFailure: true,
            body: {
              to: [{ address: params.to }],
              type: params.type ?? "message",
              subject: params.subject,
              content: { format: params.format ?? "text", body: params.body },
              ...(params.task === undefined ? {} : { task: params.task }),
              attachments: params.attachment_ids ?? [],
              priority: params.priority ?? "normal",
              requires_ack: params.requires_ack ?? true,
              metadata: params.metadata ?? {},
              expires_at: params.expires_at ?? null,
            },
          });
          return result(data, key);
        } catch (error) {
          throw safeToolError(error, key);
        }
      },
    }),
    tool({
      name: "agentpost_inbox",
      label: "List AgentPost inbox",
      description: "List one durable inbox page without changing read state.",
      parameters: Type.Object(
        {
          status: Type.Optional(Type.Union(inboxStatuses.map((value) => Type.Literal(value)))),
          sender: Type.Optional(Type.String({ maxLength: 320 })),
          type: Type.Optional(Type.Union(messageTypes.map((value) => Type.Literal(value)))),
          priority: Type.Optional(Type.Union(priorities.map((value) => Type.Literal(value)))),
          since: Type.Optional(Type.String({ format: "date-time" })),
          limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 100, default: 50 })),
          cursor: Type.Optional(Type.String({ maxLength: 2048 })),
        },
        strict,
      ),
      outputSchema: resultSchema,
      async execute(params, config, context) {
        try {
          const data = await api(config).request({
            path: "/inbox",
            signal: context.signal,
            query: {
              status: params.status,
              sender: params.sender,
              type: params.type,
              priority: params.priority,
              since: params.since,
              limit: params.limit ?? 50,
              cursor: params.cursor,
            },
          });
          return result(data);
        } catch (error) {
          throw safeToolError(error);
        }
      },
    }),
    tool({
      name: "agentpost_read",
      label: "Read AgentPost message",
      description: "Retrieve one message with GET. This does not mark it read.",
      parameters: Type.Object(
        { message_id: Type.String({ minLength: 1, maxLength: 64 }) },
        strict,
      ),
      outputSchema: resultSchema,
      async execute(params, config, context) {
        try {
          return result(
            await api(config).request({
              path: `/messages/${encodeURIComponent(params.message_id)}`,
              signal: context.signal,
            }),
          );
        } catch (error) {
          throw safeToolError(error);
        }
      },
    }),
    tool({
      name: "agentpost_reply",
      label: "Reply to AgentPost message",
      description: "Reply in the server-derived thread to the server-derived peer.",
      optional: true,
      parameters: Type.Object(
        {
          message_id: Type.String({ minLength: 1, maxLength: 64 }),
          body: Type.Unknown({ description: "Untrusted external message content." }),
          subject: Type.Optional(Type.String({ maxLength: 500 })),
          type: Type.Optional(
            Type.Union(replyMessageTypes.map((value) => Type.Literal(value))),
          ),
          format: Type.Optional(Type.Union(formats.map((value) => Type.Literal(value)))),
          task: Type.Optional(Type.Record(Type.String(), Type.Unknown())),
          result: Type.Optional(Type.Record(Type.String(), Type.Unknown())),
          attachment_ids: attachmentIds,
          priority: Type.Optional(Type.Union(priorities.map((value) => Type.Literal(value)))),
          requires_ack: Type.Optional(Type.Boolean()),
          metadata: Type.Optional(Type.Record(Type.String(), Type.Unknown())),
          expires_at: Type.Optional(Type.String({ format: "date-time" })),
          idempotency_key: idempotencyKey,
        },
        strict,
      ),
      outputSchema: resultSchema,
      async execute(params, config, context) {
        const key = params.idempotency_key ?? generatedKey();
        try {
          const data = await api(config).request({
            method: "POST",
            path: `/messages/${encodeURIComponent(params.message_id)}/reply`,
            signal: context.signal,
            idempotencyKey: key,
            acceptanceUnknownOnFailure: true,
            body: {
              type: params.type ?? "message",
              subject: params.subject ?? "",
              content: { format: params.format ?? "text", body: params.body },
              ...(params.task === undefined ? {} : { task: params.task }),
              ...(params.result === undefined ? {} : { result: params.result }),
              attachments: params.attachment_ids ?? [],
              priority: params.priority ?? "normal",
              requires_ack: params.requires_ack ?? true,
              metadata: params.metadata ?? {},
              expires_at: params.expires_at ?? null,
            },
          });
          return result(data, key);
        } catch (error) {
          throw safeToolError(error, key);
        }
      },
    }),
    tool({
      name: "agentpost_ack",
      label: "Acknowledge AgentPost message",
      description: "Idempotently acknowledge a received message. ACK also ensures read state.",
      optional: true,
      parameters: Type.Object(
        { message_id: Type.String({ minLength: 1, maxLength: 64 }) },
        strict,
      ),
      outputSchema: resultSchema,
      async execute(params, config, context) {
        try {
          return result(
            await api(config).request({
              method: "POST",
              path: `/messages/${encodeURIComponent(params.message_id)}/ack`,
              signal: context.signal,
            }),
          );
        } catch (error) {
          throw safeToolError(error);
        }
      },
    }),
    tool({
      name: "agentpost_search_agents",
      label: "Search AgentPost directory",
      description: "Search self-declared Agent profiles by text or capability.",
      parameters: Type.Object(
        {
          q: Type.Optional(Type.String({ minLength: 1, maxLength: 200 })),
          capability: Type.Optional(Type.String({ minLength: 1, maxLength: 100 })),
          limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 100, default: 20 })),
        },
        strict,
      ),
      outputSchema: resultSchema,
      async execute(params, config, context) {
        if (params.q === undefined && params.capability === undefined) {
          throw new AgentPostHttpError({
            code: "INVALID_ARGUMENT",
            message: "q or capability is required",
          });
        }
        try {
          return result(
            await api(config).request({
              path: "/directory/search",
              signal: context.signal,
              query: {
                q: params.q,
                capability: params.capability,
                limit: params.limit ?? 20,
              },
            }),
          );
        } catch (error) {
          throw safeToolError(error);
        }
      },
    }),
  ],
});
