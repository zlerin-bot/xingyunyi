"use strict";

const state = {
  humanKey: "",
  dashboard: null,
};

const elements = {
  welcomeView: document.querySelector("#welcome-view"),
  workspaceView: document.querySelector("#workspace-view"),
  accessForm: document.querySelector("#access-form"),
  accessKey: document.querySelector("#human-access-key"),
  accessResult: document.querySelector("#access-result"),
  connectionState: document.querySelector("#connection-state"),
  refresh: document.querySelector("#refresh-dashboard"),
  signOut: document.querySelector("#sign-out"),
  humanName: document.querySelector("#human-name"),
  humanEmail: document.querySelector("#human-email"),
  humanAvatar: document.querySelector("#human-avatar"),
  overviewCopy: document.querySelector("#overview-copy"),
  metricAgents: document.querySelector("#metric-agents"),
  metricUnread: document.querySelector("#metric-unread"),
  metricPending: document.querySelector("#metric-pending"),
  metricOnline: document.querySelector("#metric-online"),
  agentCount: document.querySelector("#agent-count"),
  agentList: document.querySelector("#agent-list"),
  taskList: document.querySelector("#task-list"),
  messageList: document.querySelector("#message-list"),
};

function setConnection(message, kind = "") {
  elements.connectionState.className = `connection ${kind}`.trim();
  const dot = document.createElement("span");
  dot.className = "connection-dot";
  dot.setAttribute("aria-hidden", "true");
  elements.connectionState.replaceChildren(dot, document.createTextNode(message));
}

function setFormStatus(message, kind = "") {
  elements.accessResult.className = `form-status ${kind}`.trim();
  elements.accessResult.textContent = message;
}

function humanHeaders() {
  return { Authorization: `Bearer ${state.humanKey}` };
}

function errorMessage(payload, status) {
  const error = payload && typeof payload === "object" ? payload.error : null;
  if (error && typeof error.message === "string") {
    return `无法进入星轨（${status}）：${error.message}`;
  }
  return `无法进入星轨（${status}）。`;
}

async function requestJson(path) {
  const response = await fetch(path, {
    method: "GET",
    headers: humanHeaders(),
    cache: "no-store",
    credentials: "same-origin",
    redirect: "error",
    referrerPolicy: "no-referrer",
  });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    throw new Error(errorMessage(payload, response.status));
  }
  return payload;
}

function safeText(value, fallback = "—") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  return typeof value === "object" ? JSON.stringify(value, null, 2) : String(value);
}

function dateText(value) {
  if (!value) {
    return "暂无活动";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return safeText(value);
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsed);
}

function emptyState(message) {
  const empty = document.createElement("div");
  empty.className = "empty-state";
  empty.textContent = message;
  return empty;
}

function statusLabel(value) {
  const labels = {
    pending: "进行中",
    completed: "已完成",
    partial: "部分完成",
    failed: "失败",
    cancelled: "已取消",
    delivered: "已投递",
    read: "已读取",
    acked: "已确认",
    active: "运行中",
    owner: "所有者",
    operator: "操作员",
    viewer: "观察者",
    auditor: "审计者",
  };
  return labels[value] || safeText(value);
}

function chip(value, type = "status") {
  const item = document.createElement("span");
  item.className = `data-chip ${type} ${safeText(value, "unknown")}`;
  item.textContent = statusLabel(value);
  return item;
}

function renderMetrics(metrics, agents) {
  elements.metricAgents.textContent = safeText(metrics.agent_count, "0");
  elements.metricUnread.textContent = safeText(metrics.unread_delivery_count, "0");
  elements.metricPending.textContent = safeText(metrics.pending_task_count, "0");
  elements.metricOnline.textContent = safeText(metrics.online_recently_count, "0");
  const active = agents.filter((agent) => agent.status === "active").length;
  elements.overviewCopy.textContent = `当前可观察 ${agents.length} 个 Agent，其中 ${active} 个身份处于 active；通信状态和工作状态在星轨中分别呈现。`;
}

function renderAgents(agents) {
  elements.agentList.replaceChildren();
  elements.agentCount.textContent = `${agents.length} 个`;
  if (agents.length === 0) {
    elements.agentList.append(emptyState("尚未绑定 Agent。请由系统管理员在不暴露 Agent API Key 的前提下授予访问关系。"));
    return;
  }
  const fragment = document.createDocumentFragment();
  agents.forEach((agent) => {
    const card = document.createElement("article");
    card.className = "agent-card";

    const top = document.createElement("div");
    top.className = "agent-card-top";
    const identity = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = safeText(agent.display_name, agent.address);
    const address = document.createElement("span");
    address.textContent = safeText(agent.address);
    identity.append(title, address);
    const role = chip(agent.role, "role");
    top.append(identity, role);

    const capabilities = document.createElement("div");
    capabilities.className = "capability-row";
    const values = Array.isArray(agent.capabilities) ? agent.capabilities.slice(0, 4) : [];
    if (values.length === 0) {
      const value = document.createElement("span");
      value.textContent = "未声明能力";
      capabilities.append(value);
    } else {
      values.forEach((capability) => {
        const value = document.createElement("span");
        value.textContent = safeText(capability);
        capabilities.append(value);
      });
    }

    const stats = document.createElement("dl");
    stats.className = "agent-stats";
    [["待处理投递", agent.unread_count], ["进行中任务", agent.pending_task_count], ["最近活动", dateText(agent.last_seen_at)]].forEach(([label, value]) => {
      const cell = document.createElement("div");
      const term = document.createElement("dt");
      term.textContent = label;
      const detail = document.createElement("dd");
      detail.textContent = safeText(value, "0");
      cell.append(term, detail);
      stats.append(cell);
    });
    card.append(top, capabilities, stats);
    fragment.append(card);
  });
  elements.agentList.append(fragment);
}

function renderTasks(tasks) {
  elements.taskList.replaceChildren();
  if (!tasks.length) {
    elements.taskList.append(emptyState("当前没有与你的 Agent 相关的 task 消息。"));
    return;
  }
  const fragment = document.createDocumentFragment();
  tasks.forEach((task) => {
    const item = document.createElement("article");
    item.className = `task-item ${safeText(task.work_state, "pending")}`;
    const marker = document.createElement("div");
    marker.className = "timeline-marker";

    const body = document.createElement("div");
    body.className = "task-body";
    const heading = document.createElement("div");
    heading.className = "task-heading";
    const title = document.createElement("strong");
    title.textContent = safeText(task.subject, "未命名任务");
    heading.append(title, chip(task.work_state));

    const route = document.createElement("p");
    route.className = "task-route";
    route.textContent = `${safeText(task.requester_address)} → ${safeText(task.assignee_address)}`;
    const instruction = document.createElement("p");
    instruction.className = "task-instruction";
    instruction.textContent = task.instruction === null ? "内容因审计角色而隐藏。" : safeText(task.instruction, "无任务说明");
    const states = document.createElement("div");
    states.className = "dual-state";
    const communication = document.createElement("span");
    communication.textContent = `通信：${statusLabel(task.communication_state)}`;
    const work = document.createElement("span");
    work.textContent = `工作：${statusLabel(task.work_state)}`;
    const time = document.createElement("span");
    time.textContent = dateText(task.updated_at);
    states.append(communication, work, time);
    body.append(heading, route, instruction, states);
    item.append(marker, body);
    fragment.append(item);
  });
  elements.taskList.append(fragment);
}

function renderMessages(messages) {
  elements.messageList.replaceChildren();
  if (!messages.length) {
    elements.messageList.append(emptyState("当前没有与你获授权 Agent 相关的通信。"));
    return;
  }
  const fragment = document.createDocumentFragment();
  messages.forEach((message) => {
    const card = document.createElement("article");
    card.className = "message-card";
    const header = document.createElement("div");
    header.className = "message-heading";
    const titleGroup = document.createElement("div");
    const type = document.createElement("span");
    type.className = "message-type";
    type.textContent = safeText(message.message_type);
    const title = document.createElement("strong");
    title.textContent = safeText(message.subject, "无主题消息");
    titleGroup.append(type, title);
    header.append(titleGroup, chip(message.communication_state));

    const route = document.createElement("p");
    route.className = "message-route";
    route.textContent = `${safeText(message.sender_address)} → ${safeText(message.recipient_address)} · ${dateText(message.created_at)}`;
    const content = document.createElement("pre");
    content.textContent = message.content_redacted
      ? "正文因审计角色而隐藏。"
      : safeText(message.content_body, "无正文");
    const footer = document.createElement("div");
    footer.className = "message-footer";
    const trust = document.createElement("span");
    trust.textContent = safeText(message.security_label);
    const identifier = document.createElement("span");
    identifier.textContent = safeText(message.message_id);
    footer.append(trust, identifier);
    card.append(header, route, content, footer);
    fragment.append(card);
  });
  elements.messageList.append(fragment);
}

function renderDashboard(dashboard) {
  state.dashboard = dashboard;
  const user = dashboard.user || {};
  const agents = Array.isArray(dashboard.agents) ? dashboard.agents : [];
  const tasks = Array.isArray(dashboard.tasks) ? dashboard.tasks : [];
  const messages = Array.isArray(dashboard.recent_messages) ? dashboard.recent_messages : [];
  elements.humanName.textContent = safeText(user.display_name, "星轨用户");
  elements.humanEmail.textContent = safeText(user.email);
  elements.humanAvatar.textContent = safeText(user.display_name, "星").slice(0, 1);
  renderMetrics(dashboard.metrics || {}, agents);
  renderAgents(agents);
  renderTasks(tasks);
  renderMessages(messages);
}

async function loadDashboard() {
  elements.refresh.disabled = true;
  setConnection("正在同步星轨", "loading");
  try {
    const dashboard = await requestJson("/api/v1/orbit/dashboard");
    renderDashboard(dashboard);
    elements.welcomeView.hidden = true;
    elements.workspaceView.hidden = false;
    setConnection("星轨已连接", "success");
  } catch (error) {
    setConnection("星轨连接失败", "error");
    throw error;
  } finally {
    elements.refresh.disabled = false;
  }
}

async function enterOrbit(event) {
  event.preventDefault();
  const submit = elements.accessForm.querySelector("button[type='submit']");
  submit.disabled = true;
  const candidate = elements.accessKey.value.trim();
  if (!candidate.startsWith("hum_") || candidate.length < 20) {
    setFormStatus("请输入有效的 hum_ 人类访问密钥。", "error");
    submit.disabled = false;
    return;
  }
  state.humanKey = candidate;
  setFormStatus("正在验证身份并读取授权关系…");
  try {
    await loadDashboard();
    setFormStatus("身份验证成功。", "success");
  } catch (error) {
    state.humanKey = "";
    setFormStatus(error.message, "error");
  } finally {
    submit.disabled = false;
  }
}

function signOut() {
  state.humanKey = "";
  state.dashboard = null;
  elements.accessKey.value = "";
  elements.workspaceView.hidden = true;
  elements.welcomeView.hidden = false;
  setFormStatus("访问密钥已从页面内存清除。", "success");
  setConnection("已退出星轨");
  elements.accessKey.focus();
}

elements.accessForm.addEventListener("submit", enterOrbit);
elements.refresh.addEventListener("click", async () => {
  try {
    await loadDashboard();
  } catch (error) {
    elements.overviewCopy.textContent = error.message;
  }
});
elements.signOut.addEventListener("click", signOut);

window.addEventListener("pagehide", () => {
  state.humanKey = "";
  elements.accessKey.value = "";
});

