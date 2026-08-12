import assert from "node:assert/strict";
import test from "node:test";

import {
  AgentPostHttpClient,
  AgentPostHttpError,
  normalizeBaseUrl,
} from "../dist/client.js";

const apiKey = "agt_test_key_material_at_least_twenty_chars";

test("GET keeps fixed server config, omits unset query values, and propagates abort signal", async () => {
  const requests = [];
  const fetchImpl = async (url, init) => {
    requests.push({ url, init });
    return new Response(JSON.stringify({ items: [] }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  };
  const controller = new AbortController();
  const client = new AgentPostHttpClient(
    { baseUrl: "https://post.example/root/", apiKey, timeoutMs: 5_000 },
    fetchImpl,
  );
  const result = await client.request({
    path: "/inbox",
    query: { status: "unread", sender: undefined, limit: 50 },
    signal: controller.signal,
  });

  assert.deepEqual(result, { items: [] });
  assert.equal(requests.length, 1);
  assert.equal(String(requests[0].url), "https://post.example/root/api/v1/inbox?status=unread&limit=50");
  assert.equal(requests[0].init.method, "GET");
  assert.equal(requests[0].init.headers.Authorization, `Bearer ${apiKey}`);
  assert.ok(requests[0].init.signal instanceof AbortSignal);
  assert.equal(requests[0].init.body, undefined);
});

test("POST forwards one idempotency key and never retries a transport failure", async () => {
  let calls = 0;
  const fetchImpl = async () => {
    calls += 1;
    throw new TypeError("network failure containing a raw secret");
  };
  const client = new AgentPostHttpClient(
    { baseUrl: "https://post.example", apiKey, timeoutMs: 5_000 },
    fetchImpl,
  );

  await assert.rejects(
    client.request({
      method: "POST",
      path: "/messages",
      body: { subject: "secret body canary" },
      idempotencyKey: "stable-retry-key",
      acceptanceUnknownOnFailure: true,
    }),
    (error) => {
      assert.ok(error instanceof AgentPostHttpError);
      assert.equal(error.publicError.code, "AGENTPOST_TRANSPORT_ERROR");
      assert.equal(error.publicError.idempotency_key, "stable-retry-key");
      assert.equal(error.publicError.acceptance_unknown, true);
      assert.doesNotMatch(error.message, /raw secret|secret body canary|agt_test/);
      return true;
    },
  );
  assert.equal(calls, 1);
});

test("server errors expose only the stable AgentPost envelope", async () => {
  const fetchImpl = async () =>
    new Response(
      JSON.stringify({
        error: {
          code: "DELIVERY_NOT_ALLOWED",
          message: "The recipient does not accept this delivery",
          request_id: "request-safe",
          details: { raw_secret: "must-not-be-forwarded" },
        },
      }),
      { status: 403, headers: { Authorization: "header-secret" } },
    );
  const client = new AgentPostHttpClient(
    { baseUrl: "https://post.example", apiKey, timeoutMs: 5_000 },
    fetchImpl,
  );

  await assert.rejects(client.request({ path: "/messages/msg_hidden" }), (error) => {
    assert.deepEqual(error.publicError, {
      code: "DELIVERY_NOT_ALLOWED",
      message: "The recipient does not accept this delivery",
      status_code: 403,
      request_id: "request-safe",
      idempotency_key: undefined,
      acceptance_unknown: false,
    });
    assert.doesNotMatch(error.message, /must-not-be-forwarded|header-secret|agt_test/);
    return true;
  });
});

test("base URL validation rejects non-HTTP and credential-bearing URLs", () => {
  assert.equal(normalizeBaseUrl("https://post.example/"), "https://post.example");
  assert.throws(() => normalizeBaseUrl("file:///tmp/socket"));
  assert.throws(() => normalizeBaseUrl("https://user:password@post.example"));
  assert.throws(() => normalizeBaseUrl("https://post.example?target=other"));
});
