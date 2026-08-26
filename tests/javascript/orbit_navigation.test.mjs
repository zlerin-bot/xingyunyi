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

test("brand uses the XY-squared orbit lockup from the approved visual direction", () => {
  assert.match(html, /class="brand-lockup" viewBox="0 0 300 90"/);
  assert.match(html, /class="brand-monogram"[^>]*>XY</);
  assert.match(html, /class="brand-superscript"[^>]*>2</);
  assert.match(html, /brand-orbit-path/);
  assert.match(html, /brand-relay-node/);
  assert.match(html, /brand-ai-spark/);
  assert.match(html, />星云驿<\/text>/);
  assert.match(html, />XINGYUN RELAY<\/text>/);
  assert.match(stylesheet, /\.brand-lockup-background \{[\s\S]*?fill: #06122e;/);
  assert.match(stylesheet, /\.brand-lockup \{[\s\S]*?width: 220px;/);
  assert.match(stylesheet, /\.brand-lockup \{[\s\S]*?width: 190px;/);
  assert.match(stylesheet, /"Google Sans"/);
});

test("footer exposes the official ICP filing record on every view", () => {
  assert.match(html, /京ICP备2026049737号/);
  assert.match(html, /href="https:\/\/beian\.miit\.gov\.cn\/"/);
  assert.match(html, /rel="noopener noreferrer"/);
  assert.match(stylesheet, /\.filing-record/);
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

test("new Agent guide offers six host-specific paths in the product order", () => {
  const pickerStart = html.indexOf('class="pairing-host-picker"');
  const pickerEnd = html.indexOf("</fieldset>", pickerStart);
  const picker = html.slice(pickerStart, pickerEnd);
  const hosts = [...picker.matchAll(/data-connector-type="([^"]+)"/g)]
    .map((match) => match[1]);

  assert.deepEqual(hosts, ["workbuddy", "doubao_work", "openclaw", "hermes", "codex", "manus"]);
  assert.match(script, /doubao_work: \{ name: "豆包工作", code: "AP-DOUBAO-WORK-V1", connectionMode: "remote_mcp_oauth" \}/);
  assert.match(script, /manus: \{ name: "Manus", code: "AP-MANUS-V1", connectionMode: "remote_mcp_oauth" \}/);
  assert.match(script, /hermes: \{ name: "Hermes", code: "AP-HERMES-V1" \}/);
  assert.match(script, /使用 \$\{selected\.name\} 内置的 Custom MCP 连接/);
  assert.match(script, /不能改用长期密钥或假装已连接/);
  assert.match(stylesheet, /\.pairing-host-picker\s*\{[^}]*repeat\(3, minmax\(0, 1fr\)\)/s);
  assert.match(stylesheet, /@media \(max-width: 580px\)[\s\S]*\.pairing-host-picker\s*\{\s*grid-template-columns: 1fr/);
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

test("organization governance explains all roles and requires explicit invitation consent", () => {
  const organizationsStart = html.indexOf('id="organizations"');
  const organizationsEnd = html.indexOf("</section>", organizationsStart);
  const organizationsPanel = html.slice(organizationsStart, organizationsEnd);
  for (const role of ["Owner", "Admin", "Member", "Auditor"]) {
    assert.match(organizationsPanel, new RegExp(`>${role}<`));
  }
  assert.match(organizationsPanel, /不会自动拥有或冒充组织 Agent/);
  assert.match(organizationsPanel, /不能连接、重命名、断开或删除 Agent/);
  assert.match(organizationsPanel, /正文、附件内容、审批理由和参数保持隐藏/);

  assert.match(html, /id="organization-invitation-dialog"/);
  assert.match(html, /加入前请确认组织、角色和权限范围/);
  assert.match(html, /个人 Agent、个人对话和直接 Agent 授权不会因加入组织而自动共享/);
  assert.match(script, /maybePreviewOrganizationInvitation/);
  assert.doesNotMatch(script, /maybeAcceptOrganizationInvitation/);
  assert.match(script, /\/api\/v1\/orbit\/organization-invitations\/preview/);
  assert.match(script, /organizationInvitationForm\.addEventListener\("submit", acceptOrganizationInvitation\)/);
});

test("organization role controls mirror the server authorization boundary", () => {
  assert.match(script, /owner: Object\.freeze\(\{/);
  assert.match(script, /admin: Object\.freeze\(\{/);
  assert.match(script, /member: Object\.freeze\(\{/);
  assert.match(script, /auditor: Object\.freeze\(\{/);
  assert.match(script, /actorRole === "owner" \? \["member", "auditor", "admin"\] : \["member", "auditor"\]/);
  assert.match(script, /organizationInviteSection\.hidden = !isManager/);
  assert.match(script, /organization\?\.membership_role === "owner" && ownerCount <= 1/);
  assert.match(script, /最后一名 Owner 不能直接退出/);
  assert.match(script, /退出后只撤销组织派生权限，个人和直接授权保持不变/);
});
