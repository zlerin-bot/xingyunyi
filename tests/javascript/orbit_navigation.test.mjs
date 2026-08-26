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

test("Star Orbit opens directly on conversations without a duplicate overview", () => {
  assert.doesNotMatch(html, /data-section="overview"/);
  assert.doesNotMatch(html, /协作总览/);
  assert.match(script, /defaultSection: "communications"/);
  assert.match(script, /orbit: "communications"/);
});

test("brand uses a unique multi-colour orbit logo and system-first typography", () => {
  assert.match(html, /class="brand-mark" viewBox="0 0 48 48"/);
  assert.match(html, /brand-orbit-blue/);
  assert.match(html, /brand-orbit-red/);
  assert.match(html, /brand-orbit-yellow/);
  assert.match(html, /brand-orbit-green/);
  assert.match(stylesheet, /"Google Sans"/);
  assert.match(stylesheet, /--google-blue: #1a73e8/);
});

test("mobile navigation remains a three-entry bottom bar", () => {
  assert.match(stylesheet, /@media \(max-width: 860px\)/);
  assert.match(stylesheet, /\.workspace-sidebar \{[\s\S]*?position: fixed;[\s\S]*?inset: auto 0 0;/);
  assert.match(stylesheet, /\.primary-navigation \{[\s\S]*?display: flex;/);
  assert.match(script, /window\.scrollTo\(\{ top: 0, left: 0, behavior: "auto" \}\)/);
});

test("human activity does not reuse Agent read or ACK state", () => {
  assert.match(html, /“新动态”不会复用 Agent 的 read 或 ACK/);
  assert.match(html, /打开本时间线不会替任何 Agent 执行 read 或 ACK/);
  assert.match(script, /delivered: "已送达"/);
  assert.match(script, /read: "Agent 已读取"/);
  assert.match(script, /acked: "Agent 已确认收到"/);
  const communicationStart = html.indexOf('id="communications"');
  const communicationEnd = html.indexOf("</section>", communicationStart);
  const communicationPanel = html.slice(communicationStart, communicationEnd);
  assert.doesNotMatch(communicationPanel, /chat-composer|message-input|<textarea|type="submit"/);
});

test("Orbit conversations are Thread-based, searchable, and deep-linkable", () => {
  assert.match(html, /按 Thread 聚合/);
  assert.match(html, /主题、Agent、正文或附件名/);
  assert.match(html, /data-thread-filter="new" aria-disabled="true"/);
  assert.match(html, /data-thread-filter="action" aria-disabled="true"/);
  assert.match(script, /\/api\/v1\/orbit\/threads\?/);
  assert.match(script, /\/api\/v1\/orbit\/threads\/\$\{encodeURIComponent\(threadId\)\}/);
  assert.match(script, /thread: state\.selectedThreadId/);
  assert.match(script, /state\.threadOrganization/);
});

test("Thread timeline keeps communication, work, replies, and system events distinct", () => {
  assert.match(script, /document\.createTextNode\("通信状态"\)/);
  assert.match(script, /document\.createTextNode\("工作状态"\)/);
  assert.match(script, /replied: "已回复"/);
  assert.match(script, /thread-reply-reference/);
  assert.match(script, /scrollIntoView/);
  assert.match(script, /\["event", "system", "error"\]/);
  assert.match(script, /message\.task_expected_output/);
  assert.match(script, /message\.requires_ack \? "是" : "否"/);
  assert.match(script, /来自 Agent 的不可信外部内容/);
  assert.match(script, /thread-message-content-\$\{contentFormat\}/);
  assert.match(stylesheet, /pre\.thread-message-content-json/);
});

test("mobile Thread list and detail are separate layers", () => {
  assert.match(stylesheet, /thread-workspace-mode:not\(\.thread-detail-open\).*?\.workspace-content/s);
  assert.match(stylesheet, /thread-workspace-mode\.thread-detail-open \.context-sidebar/);
  assert.match(html, /返回对话列表/);
});

test("Relay groups Agents and derives five explicit connection states", () => {
  assert.match(html, /我的 Agent/);
  assert.match(html, /全部 Agent/);
  assert.match(html, /正常连接/);
  assert.match(html, /等待 Agent/);
  assert.match(html, /离线/);
  assert.match(html, /连接异常/);
  assert.match(script, /connection_state/);
  assert.match(script, /current_connector_last_heartbeat_at/);
  assert.match(script, /Human 已授权，等待 Agent/);
  assert.match(script, /曾经连接，但最近报到已超时/);
});

test("Agent detail keeps current connection, history, access and actions distinct", () => {
  for (const tab of ["summary", "connection", "capabilities", "access", "history", "threads", "danger"]) {
    assert.match(html, new RegExp(`data-agent-tab="${tab}"`));
  }
  assert.match(html, /重新连接这个 Agent/);
  assert.match(html, /历史连接/);
  assert.match(html, /删除采用软删除/);
  assert.match(script, /connector\.is_current && connector\.status === "active"/);
  assert.match(script, /agent\.role === "owner"/);
  assert.match(script, /按钮显示不代替服务端鉴权/);
  assert.match(script, /\/api\/v1\/orbit\/threads\?limit=200&agent_id=/);
});

test("Agent selection and tab survive deep links and browser history", () => {
  assert.match(script, /parameters\.get\("agent"\)/);
  assert.match(script, /parameters\.get\("agentTab"\)/);
  assert.match(script, /agent: state\.selectedAgentId/);
  assert.match(script, /agentTab: state\.agentTab/);
  assert.match(script, /applyAgentRouteParameters\(parameters\)/);
  assert.match(script, /returnThread/);
});

test("mobile Agent list and detail are separate layers", () => {
  assert.match(stylesheet, /agent-workspace-mode:not\(\.agent-detail-open\).*?\.workspace-content/s);
  assert.match(stylesheet, /agent-workspace-mode\.agent-detail-open \.context-sidebar/);
  assert.match(html, /返回 Agent 列表/);
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
