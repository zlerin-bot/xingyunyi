export class AgentPostError extends Error {
    code;
    statusCode;
    requestId;
    idempotencyKey;
    acceptanceUnknown;
    constructor(options) {
        super(options.message);
        this.name = "AgentPostError";
        this.code = options.code;
        this.statusCode = options.statusCode;
        this.requestId = options.requestId;
        this.idempotencyKey = options.idempotencyKey;
        this.acceptanceUnknown = options.acceptanceUnknown ?? false;
    }
}
export function normalizeServer(value) {
    const url = new URL(value.trim());
    if (!["http:", "https:"].includes(url.protocol)) {
        throw new AgentPostError({ code: "INVALID_CONFIGURATION", message: "server must use HTTP(S)" });
    }
    if (url.username || url.password || url.search || url.hash) {
        throw new AgentPostError({
            code: "INVALID_CONFIGURATION",
            message: "server must not contain credentials, query, or fragment",
        });
    }
    url.pathname = url.pathname.replace(/\/+$/, "");
    return url.toString().replace(/\/$/, "");
}
function idempotencyKey() {
    return `ts_${globalThis.crypto.randomUUID()}`;
}
async function parseResponse(response, options = {}) {
    let payload;
    try {
        payload = await response.json();
    }
    catch {
        throw new AgentPostError({
            code: "MALFORMED_RESPONSE",
            message: "AgentPost returned malformed JSON",
            statusCode: response.status,
            idempotencyKey: options.idempotencyKey,
            acceptanceUnknown: options.acceptanceUnknown,
        });
    }
    if (!response.ok) {
        const envelope = payload;
        throw new AgentPostError({
            code: String(envelope?.error?.code ?? "AGENTPOST_REQUEST_FAILED"),
            message: String(envelope?.error?.message ?? "AgentPost request failed"),
            statusCode: response.status,
            requestId: typeof envelope?.error?.request_id === "string" ? envelope.error.request_id : undefined,
            idempotencyKey: options.idempotencyKey,
        });
    }
    return payload;
}
export class AgentPostClient {
    server;
    connectorId;
    agentAddress;
    #fetch;
    #timeoutMs;
    #apiKey;
    constructor(options) {
        this.server = normalizeServer(options.server);
        if (!options.apiKey.startsWith("agt_") || options.apiKey.length < 20) {
            throw new AgentPostError({ code: "INVALID_CONFIGURATION", message: "apiKey is invalid" });
        }
        this.#apiKey = options.apiKey;
        this.#fetch = options.fetch ?? globalThis.fetch;
        this.#timeoutMs = options.timeoutMs ?? 30_000;
        if (this.#timeoutMs < 100 || this.#timeoutMs > 120_000) {
            throw new AgentPostError({
                code: "INVALID_CONFIGURATION",
                message: "timeoutMs must be between 100 and 120000",
            });
        }
    }
    toString() {
        return `AgentPostClient(${this.server})`;
    }
    async request(method, path, options = {}) {
        const target = new URL(`${this.server}/api/v1${path}`);
        for (const [key, value] of Object.entries(options.query ?? {})) {
            if (value !== null && value !== undefined)
                target.searchParams.set(key, String(value));
        }
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), this.#timeoutMs);
        const abort = () => controller.abort(options.signal?.reason);
        options.signal?.addEventListener("abort", abort, { once: true });
        try {
            const headers = {
                Accept: "application/json",
                Authorization: `Bearer ${this.#apiKey}`,
            };
            if (options.body !== undefined)
                headers["Content-Type"] = "application/json";
            if (options.idempotencyKey)
                headers["Idempotency-Key"] = options.idempotencyKey;
            let response;
            try {
                response = await this.#fetch(target, {
                    method,
                    headers,
                    body: options.body === undefined ? undefined : JSON.stringify(options.body),
                    signal: controller.signal,
                    redirect: "error",
                });
            }
            catch {
                throw new AgentPostError({
                    code: controller.signal.aborted ? "REQUEST_ABORTED" : "TRANSPORT_ERROR",
                    message: controller.signal.aborted
                        ? "AgentPost request was aborted or timed out"
                        : "AgentPost transport did not complete",
                    idempotencyKey: options.idempotencyKey,
                    acceptanceUnknown: options.acceptanceUnknown,
                });
            }
            return await parseResponse(response, options);
        }
        finally {
            clearTimeout(timeout);
            options.signal?.removeEventListener("abort", abort);
        }
    }
    async send(options) {
        const key = options.idempotencyKey ?? idempotencyKey();
        const type = options.type ?? "message";
        const task = type === "task" && options.task === undefined
            ? { instruction: String(options.body) }
            : options.task;
        return await this.request("POST", "/messages", {
            idempotencyKey: key,
            acceptanceUnknown: true,
            body: {
                to: [{ address: options.to }],
                type,
                subject: options.subject,
                content: { format: options.format ?? "text", body: options.body },
                task,
                attachments: options.attachments ?? [],
                priority: "normal",
                requires_ack: true,
                metadata: options.metadata ?? {},
            },
        });
    }
    async inbox(options = {}) {
        return await this.request("GET", "/inbox", {
            query: { status: options.status, cursor: options.cursor, limit: options.limit ?? 50 },
        });
    }
    async read(messageId) {
        return await this.request("POST", `/messages/${encodeURIComponent(messageId)}/read`);
    }
    async ack(messageId) {
        return await this.request("POST", `/messages/${encodeURIComponent(messageId)}/ack`);
    }
    async reply(messageId, options) {
        const key = options.idempotencyKey ?? idempotencyKey();
        return await this.request("POST", `/messages/${encodeURIComponent(messageId)}/reply`, {
            idempotencyKey: key,
            acceptanceUnknown: true,
            body: {
                type: options.type ?? "message",
                subject: options.subject ?? "",
                content: { format: "text", body: options.body },
                attachments: [],
                priority: "normal",
                requires_ack: true,
                metadata: {},
            },
        });
    }
    async search(options) {
        if (!options.q && !options.capability) {
            throw new AgentPostError({
                code: "INVALID_CONFIGURATION",
                message: "q or capability is required",
            });
        }
        const payload = await this.request("GET", "/directory/search", {
            query: { q: options.q, capability: options.capability, limit: options.limit ?? 20 },
        });
        return payload.items;
    }
    async heartbeat(healthStatus = "healthy", lastErrorCode) {
        return await this.request("POST", "/connect/heartbeat", {
            body: { health_status: healthStatus, last_error_code: lastErrorCode ?? null },
        });
    }
    async rotateCredential() {
        const payload = await this.request("POST", "/connect/credentials/rotate");
        if (!payload.api_key?.startsWith("agt_")) {
            throw new AgentPostError({ code: "MALFORMED_RESPONSE", message: "Rotation response is invalid" });
        }
        this.#apiKey = payload.api_key;
        return { connector_id: payload.connector_id, agent: payload.agent, rotated_at: payload.rotated_at };
    }
    credentialSnapshot(profile) {
        if (!this.connectorId || !this.agentAddress) {
            throw new AgentPostError({
                code: "INVALID_STATE",
                message: "Connector identity is not available",
            });
        }
        return {
            server: this.server,
            profile,
            connectorId: this.connectorId,
            agentAddress: this.agentAddress,
            apiKey: this.#apiKey,
        };
    }
}
export class PairingSession {
    instructions;
    #server;
    #deviceCode;
    #fetch;
    #timeoutMs;
    constructor(options) {
        this.#server = options.server;
        this.instructions = options.instructions;
        this.#deviceCode = options.deviceCode;
        this.#fetch = options.fetch;
        this.#timeoutMs = options.timeoutMs;
    }
    toString() {
        return `PairingSession(${this.instructions.pairing_id})`;
    }
    async poll() {
        let response;
        try {
            response = await this.#fetch(`${this.#server}/api/v1/connect/pairings/token`, {
                method: "POST",
                headers: { Accept: "application/json", "Content-Type": "application/json" },
                body: JSON.stringify({ device_code: this.#deviceCode }),
                redirect: "error",
            });
        }
        catch {
            throw new AgentPostError({ code: "TRANSPORT_ERROR", message: "Pairing poll failed" });
        }
        const payload = await parseResponse(response);
        if (response.status === 202 || payload.status === "pending")
            return null;
        if (payload.status !== "approved" || !payload.api_key) {
            throw new AgentPostError({ code: "MALFORMED_RESPONSE", message: "Pairing result is invalid" });
        }
        const client = new AgentPostClient({
            server: this.#server,
            apiKey: payload.api_key,
            fetch: this.#fetch,
            timeoutMs: this.#timeoutMs,
        });
        client.connectorId = payload.connector?.connector_id;
        client.agentAddress = payload.agent?.address;
        return client;
    }
    async wait(options = {}) {
        const timeoutMs = options.timeoutMs ?? 15 * 60_000;
        const sleeper = options.sleeper ?? ((milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds)));
        const deadline = Date.now() + timeoutMs;
        while (Date.now() < deadline) {
            const client = await this.poll();
            if (client)
                return client;
            await sleeper(Math.max(1_000, this.instructions.interval * 1_000));
        }
        throw new AgentPostError({ code: "PAIRING_TIMEOUT", message: "Pairing authorization timed out" });
    }
}
export async function beginPairing(options) {
    const server = normalizeServer(options.server);
    const fetchImpl = options.fetch ?? globalThis.fetch;
    let response;
    try {
        response = await fetchImpl(`${server}/api/v1/connect/pairings`, {
            method: "POST",
            headers: { Accept: "application/json", "Content-Type": "application/json" },
            body: JSON.stringify({
                connector_type: options.connectorType,
                display_name: options.displayName,
                device_name: options.deviceName ?? null,
                client_version: options.clientVersion ?? null,
                capabilities: options.capabilities ?? [],
            }),
            redirect: "error",
        });
    }
    catch {
        throw new AgentPostError({ code: "TRANSPORT_ERROR", message: "Pairing request failed" });
    }
    const payload = await parseResponse(response);
    if (!payload.device_code?.startsWith("dvc_")) {
        throw new AgentPostError({ code: "MALFORMED_RESPONSE", message: "Pairing response is invalid" });
    }
    const instructions = {
        pairing_id: payload.pairing_id,
        user_code: payload.user_code,
        verification_uri: payload.verification_uri,
        verification_uri_complete: payload.verification_uri_complete,
        expires_at: payload.expires_at,
        interval: payload.interval,
    };
    return new PairingSession({
        server,
        instructions,
        deviceCode: payload.device_code,
        fetch: fetchImpl,
        timeoutMs: options.timeoutMs ?? 30_000,
    });
}
export class ManagedConnector {
    client;
    profile;
    #store;
    constructor(client, profile, store) {
        this.client = client;
        this.profile = profile;
        this.#store = store;
    }
    async rotateCredential() {
        await this.client.rotateCredential();
        await this.#store.save(this.client.credentialSnapshot(this.profile));
    }
    async forget() {
        await this.#store.delete(this.client.server, this.profile);
    }
}
export async function connectManaged(options) {
    const server = normalizeServer(options.server);
    const profile = (options.profile ?? `${options.connectorType}:${options.deviceName ?? options.displayName}`).trim();
    if (!profile || profile.length > 200) {
        throw new AgentPostError({ code: "INVALID_CONFIGURATION", message: "profile is invalid" });
    }
    const stored = await options.credentialStore.load(server, profile);
    if (stored) {
        const client = new AgentPostClient({
            server,
            apiKey: stored.apiKey,
            fetch: options.fetch,
            timeoutMs: options.timeoutMs,
        });
        client.connectorId = stored.connectorId;
        client.agentAddress = stored.agentAddress;
        try {
            await client.heartbeat();
            return new ManagedConnector(client, profile, options.credentialStore);
        }
        catch (error) {
            if (!(error instanceof AgentPostError) || error.statusCode !== 401)
                throw error;
            await options.credentialStore.delete(server, profile);
        }
    }
    const pairing = await beginPairing({
        server,
        connectorType: options.connectorType,
        displayName: options.displayName,
        deviceName: options.deviceName,
        clientVersion: options.clientVersion,
        capabilities: options.capabilities,
        fetch: options.fetch,
        timeoutMs: options.timeoutMs,
    });
    await options.onPairing?.(pairing.instructions);
    const client = await pairing.wait({
        timeoutMs: options.pairingTimeoutMs,
        sleeper: options.sleeper,
    });
    await options.credentialStore.save(client.credentialSnapshot(profile));
    return new ManagedConnector(client, profile, options.credentialStore);
}
export class ConnectorWorker {
    #connector;
    #handler;
    #cursorStore;
    constructor(options) {
        this.#connector = options.connector;
        this.#handler = options.handler;
        this.#cursorStore = options.cursorStore;
    }
    async runOnce(maxMessages = 50) {
        if (maxMessages < 1 || maxMessages > 100) {
            throw new AgentPostError({ code: "INVALID_CONFIGURATION", message: "maxMessages is invalid" });
        }
        let cursor = await this.#cursorStore.load();
        let processed = 0;
        await this.#connector.client.heartbeat();
        while (processed < maxMessages) {
            const page = await this.#connector.client.inbox({ cursor: cursor ?? undefined, limit: 1 });
            if (!page.items.length)
                break;
            let message = page.items[0];
            try {
                if (message.delivery.status === "delivered") {
                    message = await this.#connector.client.read(message.message_id);
                }
                await this.#handler(message);
                if (message.delivery.status !== "acked") {
                    await this.#connector.client.ack(message.message_id);
                }
            }
            catch (error) {
                try {
                    await this.#connector.client.heartbeat("degraded", "MESSAGE_HANDLER_ERROR");
                }
                catch {
                    // Preserve the original handler failure and the previous durable cursor.
                }
                throw error;
            }
            if (page.next_cursor) {
                cursor = page.next_cursor;
                await this.#cursorStore.save(cursor);
            }
            processed += 1;
            if (!page.has_more)
                break;
        }
        await this.#connector.client.heartbeat();
        return processed;
    }
}
//# sourceMappingURL=index.js.map