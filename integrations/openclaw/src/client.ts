export type AgentPostPluginConfig = {
  baseUrl: string;
  apiKey: string;
  timeoutMs?: number;
};

export type RequestOptions = {
  method?: "GET" | "POST";
  path: string;
  query?: Record<string, string | number | boolean | null | undefined>;
  body?: unknown;
  idempotencyKey?: string;
  signal?: AbortSignal;
  acceptanceUnknownOnFailure?: boolean;
};

export type PublicToolError = {
  code: string;
  message: string;
  status_code?: number;
  request_id?: string;
  idempotency_key?: string;
  acceptance_unknown?: boolean;
};

export class AgentPostHttpError extends Error {
  readonly publicError: PublicToolError;

  constructor(error: PublicToolError) {
    super(JSON.stringify(error));
    this.name = "AgentPostHttpError";
    this.publicError = error;
  }
}

export function normalizeBaseUrl(value: string): string {
  const url = new URL(value);
  if (!(["http:", "https:"] as string[]).includes(url.protocol)) {
    throw new Error("baseUrl must use HTTP or HTTPS");
  }
  if (url.username || url.password || url.search || url.hash) {
    throw new Error("baseUrl must not contain credentials, query, or fragment");
  }
  url.pathname = url.pathname.replace(/\/+$/, "");
  return url.toString().replace(/\/$/, "");
}

function publicError(
  error: unknown,
  fallback: Pick<PublicToolError, "code" | "message">,
): PublicToolError {
  if (error instanceof AgentPostHttpError) return error.publicError;
  return fallback;
}

export class AgentPostHttpClient {
  readonly baseUrl: string;
  readonly timeoutMs: number;
  readonly #apiKey: string;
  readonly #fetch: typeof fetch;

  constructor(config: AgentPostPluginConfig, fetchImpl: typeof fetch = globalThis.fetch) {
    this.baseUrl = normalizeBaseUrl(config.baseUrl);
    this.timeoutMs = config.timeoutMs ?? 30_000;
    if (!config.apiKey || config.apiKey.length < 20) throw new Error("apiKey is required");
    if (this.timeoutMs < 100 || this.timeoutMs > 120_000) {
      throw new Error("timeoutMs must be between 100 and 120000");
    }
    this.#apiKey = config.apiKey;
    this.#fetch = fetchImpl;
  }

  async request(options: RequestOptions): Promise<unknown> {
    const method = options.method ?? "GET";
    const target = new URL(`${this.baseUrl}/api/v1${options.path}`);
    for (const [key, value] of Object.entries(options.query ?? {})) {
      if (value !== undefined && value !== null) target.searchParams.set(key, String(value));
    }
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(new Error("request timeout")), this.timeoutMs);
    const abort = () => controller.abort(options.signal?.reason);
    options.signal?.addEventListener("abort", abort, { once: true });
    try {
      const headers: Record<string, string> = {
        Accept: "application/json",
        Authorization: `Bearer ${this.#apiKey}`,
      };
      if (options.body !== undefined) headers["Content-Type"] = "application/json";
      if (options.idempotencyKey) headers["Idempotency-Key"] = options.idempotencyKey;
      const response = await this.#fetch(target, {
        method,
        headers,
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
        signal: controller.signal,
        redirect: "error",
      });
      let payload: unknown;
      try {
        payload = await response.json();
      } catch {
        throw new AgentPostHttpError({
          code: "AGENTPOST_PROTOCOL_ERROR",
          message: "AgentPost returned malformed JSON",
          status_code: response.status,
          idempotency_key: options.idempotencyKey,
          acceptance_unknown: options.acceptanceUnknownOnFailure,
        });
      }
      if (!response.ok) {
        const envelope = payload as {
          error?: { code?: unknown; message?: unknown; request_id?: unknown };
        };
        throw new AgentPostHttpError({
          code: String(envelope?.error?.code ?? "AGENTPOST_REQUEST_FAILED"),
          message: String(envelope?.error?.message ?? "AgentPost request failed"),
          status_code: response.status,
          request_id:
            typeof envelope?.error?.request_id === "string"
              ? envelope.error.request_id
              : undefined,
          idempotency_key: options.idempotencyKey,
          acceptance_unknown: false,
        });
      }
      return payload;
    } catch (error) {
      const safe = publicError(error, {
        code: controller.signal.aborted ? "AGENTPOST_REQUEST_ABORTED" : "AGENTPOST_TRANSPORT_ERROR",
        message: controller.signal.aborted
          ? "AgentPost request was aborted or timed out"
          : "AgentPost transport did not complete",
      });
      if (safe.idempotency_key === undefined) safe.idempotency_key = options.idempotencyKey;
      if (safe.acceptance_unknown === undefined) {
        safe.acceptance_unknown = Boolean(
          options.acceptanceUnknownOnFailure && !(error instanceof AgentPostHttpError),
        );
      }
      throw new AgentPostHttpError(safe);
    } finally {
      clearTimeout(timeout);
      options.signal?.removeEventListener("abort", abort);
    }
  }
}

export function safeToolError(error: unknown, idempotencyKey?: string): Error {
  if (error instanceof AgentPostHttpError) return error;
  return new AgentPostHttpError({
    code: "AGENTPOST_INTERNAL_ERROR",
    message: "The AgentPost tool could not complete",
    idempotency_key: idempotencyKey,
  });
}
