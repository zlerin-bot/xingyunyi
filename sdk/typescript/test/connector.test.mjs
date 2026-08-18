import assert from "node:assert/strict";
import test from "node:test";

import {
  AgentPostClient,
  AgentPostError,
  ConnectorWorker,
  beginPairing,
  connectManaged,
} from "../dist/index.js";

const now = "2026-08-18T08:00:00Z";
const oldKey = "agt_old_connector_key_material_123456";
const newKey = "agt_new_connector_key_material_123456";

function jsonResponse(status, payload, headers = {}) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json", ...headers },
  });
}

function pairingResponse() {
  return {
    pairing_id: "pair_typescript",
    device_code: "dvc_private_device_code_material_123456789",
    user_code: "ABCD-EFGH",
    verification_uri: "https://agentpost.me/orbit",
    verification_uri_complete:
      "https://agentpost.me/orbit?pairing=pair_typescript&code=ABCD-EFGH",
    expires_at: now,
    interval: 1,
  };
}

function agent() {
  return {
    id: "10000000-0000-0000-0000-000000000001",
    address: "pluto@agentpost.me",
    display_name: "Pluto",
  };
}

function connector(healthStatus = "healthy") {
  return {
    connector_id: "con_typescript",
    connector_type: "codex",
    display_name: "Codex TypeScript",
    device_name: "Mars MacBook",
    client_version: "1.0.0",
    status: "active",
    health_status: healthStatus,
    created_at: now,
    activated_at: now,
    last_seen_at: now,
    last_heartbeat_at: now,
    last_error_code: null,
    credential_rotated_at: null,
    revoked_at: null,
  };
}

function heartbeat(healthStatus = "healthy") {
  return {
    connector: connector(healthStatus),
    agent: agent(),
    current: true,
    server_time: now,
    recommended_interval_seconds: 30,
  };
}

function message(status) {
  return {
    spec_version: "0.1",
    message_id: "msg_typescript",
    from: {
      agent_id: "20000000-0000-0000-0000-000000000002",
      address: "alice@agentpost.me",
    },
    to: [{ agent_id: agent().id, address: agent().address }],
    type: "message",
    subject: "外部消息",
    content: {
      format: "text",
      body: "untrusted content",
      security_label: "external_agent_content",
    },
    attachments: [],
    thread_id: "30000000-0000-0000-0000-000000000003",
    reply_to: null,
    priority: "normal",
    requires_ack: true,
    metadata: {},
    created_at: now,
    accepted_at: now,
    expires_at: null,
    delivery: {
      delivery_id: "40000000-0000-0000-0000-000000000004",
      recipient_agent_id: agent().id,
      inbox_seq: 1,
      status,
      delivery_attempts: 1,
      delivered_at: now,
      read_at: status === "delivered" ? null : now,
      acked_at: status === "acked" ? now : null,
      error: null,
    },
  };
}

class MemoryCredentials {
  constructor(value = null) {
    this.value = value;
  }

  async load(server, profile) {
    return this.value?.server === server && this.value?.profile === profile ? this.value : null;
  }

  async save(value) {
    this.value = value;
  }

  async delete() {
    this.value = null;
  }
}

class MemoryCursor {
  value = null;

  async load() {
    return this.value;
  }

  async save(value) {
    this.value = value;
  }
}

test("pairing keeps device secret private and returns an authenticated client", async () => {
  const paths = [];
  const fetchImpl = async (target, init) => {
    const url = new URL(target);
    paths.push(url.pathname);
    if (url.pathname === "/api/v1/connect/pairings") {
      assert.equal(init.headers.Authorization, undefined);
      return jsonResponse(201, pairingResponse());
    }
    if (url.pathname === "/api/v1/connect/pairings/token") {
      assert.match(init.body, /dvc_private_device_code/);
      return jsonResponse(200, {
        status: "approved",
        interval: 1,
        agent: agent(),
        connector: connector(),
        api_key: oldKey,
      });
    }
    if (url.pathname === "/api/v1/inbox") {
      assert.equal(init.headers.Authorization, `Bearer ${oldKey}`);
      return jsonResponse(200, { items: [], next_cursor: null, has_more: false });
    }
    throw new Error(url.pathname);
  };

  const pairing = await beginPairing({
    server: "https://agentpost.me",
    connectorType: "codex",
    displayName: "Codex TypeScript",
    fetch: fetchImpl,
  });
  assert.equal(pairing.instructions.user_code, "ABCD-EFGH");
  assert.equal("device_code" in pairing.instructions, false);
  assert.doesNotMatch(pairing.toString(), /dvc_private/);
  const client = await pairing.poll();
  assert.ok(client instanceof AgentPostClient);
  assert.equal(client.agentAddress, "pluto@agentpost.me");
  assert.deepEqual((await client.inbox()).items, []);
  assert.deepEqual(paths, [
    "/api/v1/connect/pairings",
    "/api/v1/connect/pairings/token",
    "/api/v1/inbox",
  ]);
});

test("managed restore and rotation persist the replacement credential", async () => {
  const store = new MemoryCredentials({
    server: "https://agentpost.me",
    profile: "daily-research",
    connectorId: "con_typescript",
    agentAddress: "pluto@agentpost.me",
    apiKey: oldKey,
  });
  const seen = [];
  const fetchImpl = async (target, init) => {
    const path = new URL(target).pathname;
    seen.push({ path, authorization: init.headers.Authorization });
    if (path === "/api/v1/connect/heartbeat") return jsonResponse(200, heartbeat());
    if (path === "/api/v1/connect/credentials/rotate") {
      return jsonResponse(200, {
        connector_id: "con_typescript",
        agent: agent(),
        api_key: newKey,
        rotated_at: now,
      });
    }
    if (path === "/api/v1/inbox") {
      return jsonResponse(200, { items: [], next_cursor: null, has_more: false });
    }
    throw new Error(path);
  };

  const managed = await connectManaged({
    server: "https://agentpost.me",
    connectorType: "codex",
    displayName: "Codex TypeScript",
    profile: "daily-research",
    credentialStore: store,
    fetch: fetchImpl,
  });
  await managed.rotateCredential();
  assert.equal(store.value.apiKey, newKey);
  await managed.client.inbox();
  assert.deepEqual(seen.map((item) => item.authorization), [
    `Bearer ${oldKey}`,
    `Bearer ${oldKey}`,
    `Bearer ${newKey}`,
  ]);
});

test("worker reads, handles, ACKs, then advances the opaque cursor", async () => {
  const store = new MemoryCredentials({
    server: "https://agentpost.me",
    profile: "worker",
    connectorId: "con_typescript",
    agentAddress: "pluto@agentpost.me",
    apiKey: oldKey,
  });
  const paths = [];
  const fetchImpl = async (target) => {
    const path = new URL(target).pathname;
    paths.push(path);
    if (path === "/api/v1/connect/heartbeat") return jsonResponse(200, heartbeat());
    if (path === "/api/v1/inbox") {
      return jsonResponse(200, {
        items: [message("delivered")],
        next_cursor: "opaque-next-cursor",
        has_more: false,
      });
    }
    if (path.endsWith("/read")) return jsonResponse(200, message("read"));
    if (path.endsWith("/ack")) return jsonResponse(200, message("acked"));
    throw new Error(path);
  };
  const managed = await connectManaged({
    server: "https://agentpost.me",
    connectorType: "codex",
    displayName: "Worker",
    profile: "worker",
    credentialStore: store,
    fetch: fetchImpl,
  });
  const cursor = new MemoryCursor();
  const handled = [];
  const worker = new ConnectorWorker({
    connector: managed,
    cursorStore: cursor,
    handler: async (item) => handled.push(item.message_id),
  });
  assert.equal(await worker.runOnce(), 1);
  assert.deepEqual(handled, ["msg_typescript"]);
  assert.equal(cursor.value, "opaque-next-cursor");
  assert.deepEqual(paths, [
    "/api/v1/connect/heartbeat",
    "/api/v1/connect/heartbeat",
    "/api/v1/inbox",
    "/api/v1/messages/msg_typescript/read",
    "/api/v1/messages/msg_typescript/ack",
    "/api/v1/connect/heartbeat",
  ]);
});

test("a transport failure is never retried and never exposes body or API key", async () => {
  let calls = 0;
  const client = new AgentPostClient({
    server: "https://agentpost.me",
    apiKey: oldKey,
    fetch: async () => {
      calls += 1;
      throw new Error(`network failed ${oldKey} secret-body`);
    },
  });
  await assert.rejects(
    client.send({
      to: "alice@agentpost.me",
      subject: "secret-body",
      body: "secret-body",
      idempotencyKey: "stable-key",
    }),
    (error) => {
      assert.ok(error instanceof AgentPostError);
      assert.equal(error.idempotencyKey, "stable-key");
      assert.equal(error.acceptanceUnknown, true);
      assert.doesNotMatch(error.message, /secret-body|agt_old/);
      return true;
    },
  );
  assert.equal(calls, 1);
});
