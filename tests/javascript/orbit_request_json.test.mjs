import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import test from "node:test";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const appSource = await readFile(
  resolve(repositoryRoot, "src/agentpost/orbit_ui/app.js"),
  "utf8",
);
const requestJsonStart = appSource.indexOf("async function requestJson");
const requestJsonEnd = appSource.indexOf("\nfunction safeText", requestJsonStart);

assert.notEqual(requestJsonStart, -1, "requestJson must remain defined in Orbit's app.js");
assert.notEqual(requestJsonEnd, -1, "requestJson extraction boundary must remain available");

const requestJsonSource = appSource.slice(requestJsonStart, requestJsonEnd);

function requestJsonWith(response) {
  const context = vm.createContext({
    Error,
    JSON,
    errorMessage: (_payload, status) => `request failed: ${status}`,
    fetch: async () => response,
  });
  vm.runInContext(
    `${requestJsonSource}\nglobalThis.__requestJson = requestJson;`,
    context,
  );
  return context.__requestJson;
}

test("requestJson accepts a JSON-labelled 204 response with an empty body", async () => {
  let jsonCalled = false;
  let textCalled = false;
  const requestJson = requestJsonWith({
    headers: { get: () => "application/json" },
    json: async () => {
      jsonCalled = true;
      throw new SyntaxError("Unexpected end of JSON input");
    },
    ok: true,
    status: 204,
    text: async () => {
      textCalled = true;
      return "";
    },
  });

  assert.equal(await requestJson("/api/v1/orbit/agents/test", { method: "DELETE" }), null);
  assert.equal(textCalled, true);
  assert.equal(jsonCalled, false);
});

test("requestJson still parses non-empty JSON responses", async () => {
  const requestJson = requestJsonWith({
    headers: { get: () => "application/json; charset=utf-8" },
    json: async () => {
      throw new Error("requestJson should parse the guarded response body exactly once");
    },
    ok: true,
    status: 200,
    text: async () => '{"status":"ok"}',
  });

  const result = await requestJson("/api/v1/orbit/dashboard");
  assert.equal(result.status, "ok");
});
