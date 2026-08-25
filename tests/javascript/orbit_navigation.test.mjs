import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const [html, script, stylesheet] = await Promise.all([
  readFile(resolve(repositoryRoot, "src/agentpost/orbit_ui/index.html"), "utf8"),
  readFile(resolve(repositoryRoot, "src/agentpost/orbit_ui/app.js"), "utf8"),
  readFile(resolve(repositoryRoot, "src/agentpost/orbit_ui/styles.css"), "utf8"),
]);

test("Orbit exposes exactly three named primary entrances", () => {
  const primaryNavigation = html.slice(
    html.indexOf('id="primary-navigation"'),
    html.indexOf("</nav>", html.indexOf('id="primary-navigation"')),
  );
  const modules = [...primaryNavigation.matchAll(/data-module="([^"]+)"/g)]
    .map((match) => match[1]);

  assert.deepEqual(modules, ["orbit", "relay", "settings"]);
  assert.match(primaryNavigation, />星轨</);
  assert.match(primaryNavigation, />云驿</);
  assert.match(primaryNavigation, />设置</);
  assert.match(primaryNavigation, /对话与动态/);
  assert.match(primaryNavigation, /Agent 与连接/);
  assert.match(primaryNavigation, /账户与平台/);
});

test("module and selected view survive navigation and browser history", () => {
  assert.match(script, /searchParams\.set\("module", module\)/);
  assert.match(script, /searchParams\.set\("view", section\)/);
  assert.match(script, /history\.pushState/);
  assert.match(script, /window\.addEventListener\("popstate"/);
  assert.match(script, /elements\.moduleViews\.forEach/);
});

test("mobile navigation remains a three-entry bottom bar", () => {
  assert.match(stylesheet, /@media \(max-width: 860px\)/);
  assert.match(stylesheet, /\.workspace-sidebar \{[\s\S]*?position: fixed;[\s\S]*?inset: auto 0 0;/);
  assert.match(stylesheet, /\.primary-navigation \{[\s\S]*?display: flex;/);
});

test("human activity does not reuse Agent read or ACK state", () => {
  assert.match(html, /尚未建立独立的本人查看记录/);
  assert.match(html, /不会把 Agent 的读取状态当成你是否看过/);
  assert.match(script, /delivered: "已送达"/);
  assert.match(script, /read: "Agent 已读取"/);
  assert.match(script, /acked: "Agent 已确认收到"/);
  const communicationStart = html.indexOf('id="communications"');
  const communicationEnd = html.indexOf("</section>", communicationStart);
  const communicationPanel = html.slice(communicationStart, communicationEnd);
  assert.doesNotMatch(communicationPanel, /chat-composer|message-input|<textarea|type="submit"/);
});

test("unavailable settings are explanatory, not fake controls", () => {
  for (const section of ["notifications", "privacy", "preferences"]) {
    const start = html.indexOf(`id="${section}"`);
    const end = html.indexOf("</section>", start);
    const panel = html.slice(start, end);
    assert.notEqual(start, -1);
    assert.match(panel, /尚未接入|待确认/);
    assert.doesNotMatch(panel, /<input|<select|type="submit"/);
  }
});
