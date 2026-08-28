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
  assert.match(primaryNavigation, /对话与协作/);
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

test("header matches the approved compact Xingyunyi lockup without centre navigation", () => {
  const header = html.match(/<header class="topbar">[\s\S]*?<\/header>/)?.[0] || "";
  assert.match(html, /class="brand-mark"/);
  assert.match(html, /id="brand-mark-gradient"/);
  assert.match(html, /M11 25c6-13 13-14 18-7/);
  assert.match(html, /<strong>星云驿<\/strong>/);
  assert.match(html, /<small id="brand-section">AgentPost · 星轨<\/small>/);
  assert.match(script, /elements\.brandSection\.textContent = `AgentPost · \$\{definition\.label\}`/);
  assert.doesNotMatch(header, /plane-switch/);
  assert.doesNotMatch(header, /星轨看协作/);
  assert.doesNotMatch(header, /云驿管 Agent/);
  assert.doesNotMatch(header, /设置管账户/);
  assert.match(stylesheet, /\.topbar \{[\s\S]*?min-height: 78px;/);
  assert.match(stylesheet, /\.brand-mark \{[\s\S]*?width: 40px;[\s\S]*?height: 40px;/);
  assert.match(stylesheet, /\.brand-copy strong \{[\s\S]*?font-size: 1\.375rem;/);
  assert.match(stylesheet, /\.connection \{[\s\S]*?min-width: 235px;/);
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

test("mobile Star Orbit uses two lightweight shortcuts instead of a second tab bar", () => {
  assert.match(html, /id="orbit-mobile-shortcuts"/);
  assert.match(html, /class="context-nav-item orbit-mobile-shortcut"[^>]*data-section="approvals"/);
  assert.match(html, /class="context-nav-item orbit-mobile-shortcut"[^>]*data-section="tasks"/);
  assert.match(script, /mobileShortcutIsActive/);
  assert.match(script, /mobileShortcutIsActive \? "communications" : item\.dataset\.section/);
  assert.match(stylesheet, /\.orbit-mobile-shortcuts:not\(\[hidden\]\) \{[\s\S]*?grid-template-columns: repeat\(2, minmax\(0, 1fr\)\)/);
  assert.match(stylesheet, /\.context-navigation > div\[data-context-module="orbit"\] \{\s*display: none;/);
  assert.match(stylesheet, /\.orbit-mobile-shortcut > span\.orbit-mobile-shortcut-count \{[\s\S]*?display: inline-grid;/);
  assert.match(stylesheet, /\.thread-list-item \{[\s\S]*?min-width: 0;/);
});

test("mobile connection status stays on one line and reports heartbeat-backed online Agents", () => {
  assert.match(html, /connection-label-full/);
  assert.match(html, /connection-label-compact/);
  assert.match(script, /`\$\{connectedAgentCount\} 个 Agent`/);
  assert.match(script, /`\$\{connectedAgentCount\} 个 Agent 在线`/);
  assert.match(script, /connectedAgentCount > 0 \? "success" : ""/);
  assert.match(stylesheet, /\.connection-label-compact \{\s*display: none;/);
  assert.match(stylesheet, /@media \(max-width: 580px\)[\s\S]*?\.connection \{[\s\S]*?white-space: nowrap;/);
  assert.match(stylesheet, /\.connection-label-full \{\s*display: none;/);
  assert.match(stylesheet, /\.connection-label-compact \{\s*display: inline;/);
});

test("opening a conversation remains read-only for Agent state", () => {
  assert.match(html, /放心查看，不会影响 Agent 的处理进度/);
  assert.match(html, /不会替 Agent 标记已读、确认收到或完成任务/);
  assert.match(script, /delivered: "已送达"/);
  assert.match(script, /read: "Agent 已读取"/);
  assert.match(script, /acked: "Agent 已确认收到"/);
  assert.match(script, /\/api\/v1\/orbit\/threads\/\$\{encodeURIComponent\(threadId\)\}\/viewed/);
  assert.match(script, /human_view_state = "viewed"/);
  const communicationStart = html.indexOf('id="communications"');
  const communicationEnd = html.indexOf("</section>", communicationStart);
  const communicationPanel = html.slice(communicationStart, communicationEnd);
  assert.doesNotMatch(communicationPanel, /chat-composer|message-input|<textarea|type="submit"/);
});

test("Orbit conversations are Thread-based, searchable, and deep-linkable", () => {
  assert.match(html, /按每个对话查看 Agent 之间的全部往来/);
  assert.match(html, /主题、Agent、正文或附件名/);
  assert.doesNotMatch(html, /新动态 · 待接入|待我处理 · 待接入/);
  assert.match(script, /\/api\/v1\/orbit\/threads\?/);
  assert.match(script, /\/api\/v1\/orbit\/threads\/\$\{encodeURIComponent\(threadId\)\}/);
  assert.match(script, /thread: state\.selectedThreadId/);
  assert.match(script, /state\.threadOrganization/);
});

test("conversation parent expands complete loops and shows Human unread dots", () => {
  assert.match(html, /id="thread-parent-toggle"/);
  assert.match(html, /aria-controls="thread-browser"/);
  assert.match(html, /aria-expanded="true"/);
  assert.match(html, /id="thread-unread-count"/);
  assert.match(script, /threadBrowserExpanded/);
  assert.match(script, /thread\.human_view_state === "unread"/);
  assert.match(script, /thread-unread-dot/);
  assert.match(script, /\$\{thread\.message_count\} 条往来/);
  assert.match(stylesheet, /\.thread-parent-toggle/);
  assert.match(stylesheet, /\.thread-unread-dot/);
});

test("confirmed header and timeline match the approved three-column mockup", () => {
  assert.match(html, /id="top-human-avatar"/);
  assert.match(html, /id="top-human-name"/);
  assert.match(html, /id="thread-detail-count"/);
  assert.match(html, /id="thread-detail-route"/);
  assert.match(html, /id="thread-detail-state"/);
  assert.match(script, /完整对话 · \$\{messages\.length\} 条往来/);
  assert.match(script, /发送自：\$\{agentConversationLabel\(firstMessage\.sender\)\}/);
  assert.match(script, /card\.classList\.toggle\("from-current-human"/);
  assert.match(script, /elements\.topHumanAvatar\.textContent = "我"/);
  assert.match(stylesheet, /\.top-human-avatar/);
  assert.match(stylesheet, /\.thread-message\.from-current-human/);
});

test("Thread timeline keeps communication, work, replies, and system events distinct", () => {
  assert.match(script, /const messages = \[\.\.\.chronologicalMessages\]\.sort/);
  assert.match(script, /new Date\(right\.created_at\)\.getTime\(\) - new Date\(left\.created_at\)\.getTime\(\)/);
  assert.match(script, /最新内容排在最上面/);
  assert.match(script, /messageList\.firstElementChild\?\.scrollIntoView\(\{ behavior: "smooth", block: "start" \}\)/);
  assert.match(script, /document\.createTextNode\("送达情况"\)/);
  assert.match(script, /document\.createTextNode\("任务进度"\)/);
  assert.match(script, /replied: "已回复"/);
  assert.match(script, /thread-reply-reference/);
  assert.match(script, /scrollIntoView/);
  assert.match(script, /\["event", "system", "error"\]/);
  assert.match(script, /message\.task_expected_output/);
  assert.match(script, /message\.requires_ack \? "是" : "否"/);
  assert.match(script, /由 Agent 提供 · 已按安全方式展示/);
  assert.match(script, /Agent 提供的结构化信息/);
  assert.match(script, /key === "status"/);
  assert.match(script, /查看 Agent 数据与技术信息（JSON）/);
  assert.match(script, /这些信息用于 Agent 协作和问题排查，不代表任务已经完成/);
  assert.match(script, /raw\.textContent = safeText\(message\.content_body, "null"\)/);
  assert.match(script, /summary\.addEventListener\("keydown"/);
  assert.match(script, /details\.open = !details\.open/);
  assert.match(script, /footer\.append\(trust\)/);
  assert.match(stylesheet, /\.thread-structured-summary/);
  assert.match(stylesheet, /\.thread-agent-data/);
});

test("conversation identity and attachments expose clear safe actions", () => {
  assert.match(script, /发送自：\$\{agentConversationLabel\(message\.sender\)\}/);
  assert.match(script, /发送给：\$\{agentConversationLabel\(message\.recipient, \{ currentAsMe: true \}\)\}/);
  assert.match(script, /agent\?\.owner_display_name/);
  assert.match(script, /agent\?\.owned_by_current_human/);
  assert.match(script, /打开 PDF/);
  assert.match(script, /安全预览/);
  assert.match(script, /\/api\/v1\/orbit\/attachments\/\$\{attachmentId\}/);
  assert.match(html, /id="attachment-preview-frame"[^>]*sandbox=""/);
  assert.match(stylesheet, /\.attachment-preview-dialog iframe/);
  assert.match(stylesheet, /\.thread-attachment-action/);
});

test("mobile Thread list and detail are separate layers", () => {
  assert.match(stylesheet, /thread-workspace-mode:not\(\.thread-detail-open\).*?\.workspace-content/s);
  assert.match(stylesheet, /thread-workspace-mode\.thread-detail-open \.context-sidebar/);
  assert.match(html, /返回对话列表/);
});

test("Relay groups Agents and derives five explicit connection states", () => {
  assert.match(html, /Agent 与连接/);
  assert.match(html, /全部 Agent/);
  assert.match(html, /正常连接/);
  assert.match(html, /等待 Agent/);
  assert.match(html, /离线/);
  assert.match(html, /连接异常/);
  assert.match(script, /connection_state/);
  assert.match(script, /current_connector_last_heartbeat_at/);
  assert.match(script, /你已完成授权，正在等待 Agent/);
  assert.match(script, /曾经连接，但最近报到已超时/);
});

test("new Agent guide offers six host-specific paths in the product order", () => {
  const pickerStart = html.indexOf('class="pairing-host-picker"');
  const pickerEnd = html.indexOf("</fieldset>", pickerStart);
  const picker = html.slice(pickerStart, pickerEnd);
  const hosts = [...picker.matchAll(/data-connector-type="([^"]+)"/g)]
    .map((match) => match[1]);

  assert.deepEqual(hosts, ["workbuddy", "doubao_work", "openclaw", "hermes", "codex", "manus"]);
  assert.match(script, /doubao_work: \{ name: "豆包工作", code: "AP-DOUBAO-WORK-V1", defaultHandle: "doubao", connectionMode: "local_bootstrap" \}/);
  assert.match(script, /manus: \{ name: "Manus", code: "AP-MANUS-V1", defaultHandle: "manus", connectionMode: "local_bootstrap" \}/);
  assert.match(
    script,
    /const connectionMode = selected\.connectionMode \|\| state\.authConfig\?\.host_connection_modes\?\.\[host\]/,
  );
  assert.match(script, /Custom MCP 连接和星轨网页授权直接完成接入/);
  assert.match(script, /hermes: \{ name: "Hermes", code: "AP-HERMES-V1", defaultHandle: "hermes" \}/);
  assert.match(script, /使用 \$\{selected\.name\} 内置的 Custom MCP 连接/);
  assert.match(script, /不能改用长期密钥或假装已连接/);
  assert.match(html, /<strong>Manus<\/strong>\s*<span>本地文件夹<\/span>/);
  assert.match(script, /文件生成后必须新建 Manus 任务/);
  assert.match(script, /\.\/xingyunyi status/);
  assert.match(script, /不要改用 Custom MCP 或 Remote MCP/);
  assert.match(stylesheet, /\.pairing-host-picker\s*\{[^}]*repeat\(3, minmax\(0, 1fr\)\)/s);
  assert.match(stylesheet, /@media \(max-width: 580px\)[\s\S]*\.pairing-host-picker\s*\{\s*grid-template-columns: 1fr/);
});

test("new Agent approval suggests a platform handle and explains each invalid shape", () => {
  const approvalStart = html.indexOf('id="pairing-approval"');
  const approvalEnd = html.indexOf("</section>", approvalStart);
  const approval = html.slice(approvalStart, approvalEnd);

  assert.match(script, /codex: \{ name: "Codex", code: "AP-CODEX-V1", defaultHandle: "codex" \}/);
  assert.match(script, /workbuddy: \{ name: "WorkBuddy", code: "AP-WORKBUDDY-V1", defaultHandle: "workbuddy" \}/);
  assert.match(script, /const candidate = `\$\{base\}-\$\{suffix\}`/);
  assert.match(html, /1–32 个中文、英文字母或数字/);
  assert.match(script, /\^\[\\p\{L\}\\p\{N\}-\]\+\$\/u/);
  assert.match(script, /不能使用空格、下划线或其他符号/);
  assert.match(script, /连字符不能放在开头或结尾，也不能连续使用/);
  assert.match(script, /是系统保留名称/);
  assert.match(approval, /id="pairing-handle-help"/);
  assert.doesNotMatch(approval, /pairing-mfa|双重验证验证码或恢复码/);
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
  assert.match(script, /可执行的操作以你的实际权限为准/);
  assert.match(script, /\/api\/v1\/orbit\/threads\?limit=200&agent_id=/);
});

test("Agent owners can find the short-name action in the detail heading", () => {
  const headingStart = html.indexOf('class="agent-detail-heading-actions"');
  const headingEnd = html.indexOf("</div>", headingStart);
  const headingActions = html.slice(headingStart, headingEnd);
  const dangerStart = html.indexOf('id="agent-owner-actions"');
  const dangerEnd = html.indexOf("</div>", dangerStart);
  const dangerActions = html.slice(dangerStart, dangerEnd);

  assert.match(headingActions, /id="agent-rename"/);
  assert.match(headingActions, /id="agent-set-default"/);
  assert.doesNotMatch(dangerActions, /id="agent-rename"/);
  assert.match(script, /elements\.agentRename\.hidden = !owner/);
  assert.match(script, /elements\.agentSetDefault\.hidden = !owner/);
  assert.match(script, /agent\.is_default \? "默认 Agent" : "设为默认 Agent"/);
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
  assert.match(html, /id="profile-username"/);
  assert.match(html, /id="register-username"[^>]*required/);
  assert.match(html, /用于让他人准确找到你，例如 020/);
  assert.match(script, /username: elements\.registerUsername\.value\.trim\(\)\.toLowerCase\(\)/);
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
