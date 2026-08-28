from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = REPOSITORY_ROOT / "integrations" / "openclaw"
MANIFEST_PATH = PLUGIN_ROOT / "openclaw.plugin.json"
PACKAGE_PATH = PLUGIN_ROOT / "package.json"
INDEX_PATH = PLUGIN_ROOT / "src" / "index.ts"
CLIENT_PATH = PLUGIN_ROOT / "src" / "client.ts"
DIST_CLIENT_PATH = PLUGIN_ROOT / "dist" / "client.js"

EXPECTED_TOOLS = {
    "agentpost_send",
    "agentpost_inbox",
    "agentpost_get_organization_channel",
    "agentpost_list_organization_channels",
    "agentpost_send_organization_message",
    "agentpost_read",
    "agentpost_reply",
    "agentpost_ack",
    "agentpost_search_agents",
}


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _tool_names(source: str) -> set[str]:
    return set(re.findall(r"['\"](agentpost_[a-z_]+)['\"]", source))


def test_openclaw_plugin_has_native_manifest_and_package_contract() -> None:
    required = {
        MANIFEST_PATH,
        PACKAGE_PATH,
        PLUGIN_ROOT / "tsconfig.json",
        PLUGIN_ROOT / "README.md",
        INDEX_PATH,
        CLIENT_PATH,
    }
    assert all(path.is_file() for path in required), sorted(
        str(path.relative_to(REPOSITORY_ROOT)) for path in required if not path.is_file()
    )

    package = _json(PACKAGE_PATH)
    assert package["type"] == "module"
    assert package["main"] == "./dist/index.js"
    assert package["files"] == ["dist", "openclaw.plugin.json", "README.md"]
    assert package["dependencies"] == {"typebox": "^1.1.38"}
    assert package["peerDependencies"] == {"openclaw": ">=2026.5.17"}
    assert str(package["engines"]["node"]).startswith(">=")

    manifest = _json(MANIFEST_PATH)
    serialized_manifest = json.dumps(manifest, sort_keys=True).casefold()
    assert "agentpost" in serialized_manifest
    assert "configschema" in serialized_manifest.replace("_", "")
    assert "apikey" in serialized_manifest.replace("_", "")
    assert "baseurl" in serialized_manifest.replace("_", "")


def test_plugin_is_a_native_tool_plugin_with_exact_nine_tools() -> None:
    source = _source(INDEX_PATH)
    assert 'from "openclaw/plugin-sdk/tool-plugin"' in source
    assert "defineToolPlugin" in source
    assert 'from "typebox"' in source
    assert _tool_names(source) == EXPECTED_TOOLS

    registrations = re.findall(r"\btool\s*\(\s*\{", source)
    assert len(registrations) == 9
    assert len(re.findall(r"optional\s*:\s*true", source)) == 4
    manifest = _json(MANIFEST_PATH)
    optional_tools = {
        name
        for name, metadata in manifest["toolMetadata"].items()
        if metadata.get("optional") is True
    }
    assert optional_tools == {
        "agentpost_send",
        "agentpost_send_organization_message",
        "agentpost_reply",
        "agentpost_ack",
    }


def test_model_tool_schemas_cannot_choose_transport_or_credentials() -> None:
    source = _source(INDEX_PATH).casefold()
    forbidden_schema_names = {
        "baseurl",
        "base_url",
        "endpoint",
        "apikey",
        "api_key",
        "authorization",
        "timeoutms",
        "timeout_ms",
    }
    # Admin-only configuration may appear in the plugin factory, so inspect the
    # schema declarations rather than banning these strings from the whole file.
    tool_regions = re.findall(r"\btool\s*\(\s*\{(.*?)(?=\n\s*\}\),)", source, flags=re.DOTALL)
    assert len(tool_regions) == 9
    for region in tool_regions:
        schema = region.partition("async execute")[0]
        assert "parameters:" in schema
        assert not any(name in schema for name in forbidden_schema_names)


def test_nine_tools_map_to_protocol_routes_without_read_side_effects() -> None:
    source = _source(INDEX_PATH) + "\n" + _source(CLIENT_PATH)
    compact = re.sub(r"\s+", "", source)
    assert 'method:"POST",path:"/messages"' in compact
    assert 'path:"/inbox"' in compact
    assert 'path:"/organization-channel"' in compact
    assert 'path:"/organization-channels"' in compact
    assert "/channel/messages" in source
    assert "path:`/messages/${" in compact
    assert 'path:"/directory/search"' in compact
    read_region = source.partition('name: "agentpost_read"')[2].partition("tool({")[0]
    assert 'method: "POST"' not in read_region
    assert "/read" not in source, "agentpost_read must remain a side-effect-free GET"
    assert "/ack" in source
    assert "/reply" in source


def test_message_type_and_directory_semantics_match_the_server_contract() -> None:
    source = _source(INDEX_PATH)
    send_types = source.partition("const messageTypes =")[2].partition("] as const;")[0]
    reply_types = source.partition("const replyMessageTypes =")[2].partition(";")[0]
    assert '"result"' not in send_types
    assert '"result"' in reply_types

    directory_region = source.partition('name: "agentpost_search_agents"')[2]
    assert "params.q === undefined && params.capability === undefined" in directory_region
    assert 'code: "INVALID_ARGUMENT"' in directory_region
    assert "directory search filter required" not in directory_region.casefold()


def test_client_preserves_abort_idempotency_and_sanitizes_errors() -> None:
    client = _source(CLIENT_PATH)
    lowered = client.casefold()
    assert "abortsignal" in lowered
    assert "signal" in lowered
    assert "idempotency-key" in lowered
    assert "randomuuid" in (_source(INDEX_PATH) + client).casefold()
    assert "request_id" in lowered
    assert "response.text(" not in lowered
    assert "response.headers" not in lowered
    assert "console." not in lowered
    assert not re.search(r"\b(?:retry|retries|maxattempts|max_attempts)\b", lowered)


def test_adapter_does_not_import_agentpost_server_or_framework_internals() -> None:
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in PLUGIN_ROOT.rglob("*")
        if path.is_file() and path.suffix in {".ts", ".js"}
    )
    assert "src/agentpost" not in sources
    assert "agentpost.domain" not in sources
    assert "sqlalchemy" not in sources.casefold()
    assert "fastapi" not in sources.casefold()
    assert "openclaw/" not in sources.replace("openclaw/plugin-sdk/tool-plugin", "").replace(
        "openclaw/plugin-sdk/tool-plugin", ""
    )


def _node_binary() -> Path | None:
    discovered = shutil.which("node")
    candidates = [
        Path(discovered) if discovered else None,
        Path(
            "/Users/mars113/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
        ),
    ]
    return next((candidate for candidate in candidates if candidate and candidate.is_file()), None)


def test_zero_dependency_http_client_harness(tmp_path: Path) -> None:
    node = _node_binary()
    assert node is not None, "Node runtime is required for the OpenClaw adapter harness"
    assert DIST_CLIENT_PATH.is_file()
    harness = tmp_path / "openclaw-client-harness.mjs"
    harness.write_text(
        f"""
import assert from "node:assert/strict";
import {{ pathToFileURL }} from "node:url";
const {{ AgentPostHttpClient, AgentPostHttpError, normalizeBaseUrl }} = await import(
  pathToFileURL({json.dumps(str(DIST_CLIENT_PATH))}).href
);

const apiKey = "agt_runtime_secret_that_must_not_leak";
let calls = 0;
let captured;
const successFetch = async (url, init) => {{
  calls += 1;
  captured = {{ url: String(url), init }};
  return {{
    ok: true,
    status: 201,
    async json() {{
      return {{ content: {{ body: "untrusted", security_label: "external_agent_content" }} }};
    }},
  }};
}};
const client = new AgentPostHttpClient(
  {{ baseUrl: "https://post.example/root/", apiKey, timeoutMs: 1000 }},
  successFetch,
);
const result = await client.request({{
  method: "POST",
  path: "/messages",
  query: {{ keep: "yes", omit: undefined, absent: null }},
  body: {{ content: {{ body: "hello" }} }},
  idempotencyKey: "idem-reusable",
  acceptanceUnknownOnFailure: true,
}});
assert.equal(calls, 1);
assert.equal(captured.url, "https://post.example/root/api/v1/messages?keep=yes");
assert.equal(captured.init.headers.Authorization, `Bearer ${{apiKey}}`);
assert.equal(captured.init.headers["Idempotency-Key"], "idem-reusable");
assert.equal(captured.init.redirect, "error");
assert.equal(result.content.security_label, "external_agent_content");

const rawSecret = "raw-body-secret";
const errorFetch = async () => ({{
  ok: false,
  status: 403,
  headers: {{ authorization: apiKey }},
  async json() {{
    return {{
      error: {{ code: "DELIVERY_NOT_ALLOWED", message: "Denied", request_id: "req-1" }},
      raw: rawSecret,
    }};
  }},
}});
try {{
  await new AgentPostHttpClient(
    {{ baseUrl: "https://post.example", apiKey }},
    errorFetch,
  ).request({{ path: "/inbox" }});
  assert.fail("expected sanitized HTTP error");
}} catch (error) {{
  assert.ok(error instanceof AgentPostHttpError);
  assert.equal(error.publicError.code, "DELIVERY_NOT_ALLOWED");
  assert.equal(error.publicError.message, "Denied");
  assert.equal(error.publicError.request_id, "req-1");
  const serialized = JSON.stringify(error.publicError);
  assert.equal(serialized.includes(apiKey), false);
  assert.equal(serialized.includes(rawSecret), false);
  assert.equal(serialized.toLowerCase().includes("authorization"), false);
}}

let failedCalls = 0;
const failedFetch = async () => {{
  failedCalls += 1;
  throw new Error("network details must be hidden");
}};
try {{
  await new AgentPostHttpClient(
    {{ baseUrl: "https://post.example", apiKey }},
    failedFetch,
  ).request({{
    method: "POST",
    path: "/messages",
    idempotencyKey: "idem-after-failure",
    acceptanceUnknownOnFailure: true,
  }});
  assert.fail("expected transport error");
}} catch (error) {{
  assert.ok(error instanceof AgentPostHttpError);
  assert.equal(error.publicError.idempotency_key, "idem-after-failure");
  assert.equal(error.publicError.acceptance_unknown, true);
  assert.equal(JSON.stringify(error.publicError).includes("network details"), false);
}}
assert.equal(failedCalls, 1, "the adapter must not hide retries");

assert.equal(normalizeBaseUrl("https://post.example/root/"), "https://post.example/root");
for (const invalid of [
  "file:///tmp/socket",
  "https://user:pass@post.example",
  "https://post.example/?redirect=evil",
  "https://post.example/#fragment",
]) {{
  assert.throws(() => normalizeBaseUrl(invalid));
}}
""",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [str(node), str(harness)],
        cwd=PLUGIN_ROOT,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == ""
    assert "agt_" not in completed.stderr
