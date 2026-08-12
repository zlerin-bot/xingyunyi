"use strict";

const state = {
  adminResource: "agents",
};

const elements = {
  adminToken: document.querySelector("#admin-token"),
  registrationToken: document.querySelector("#registration-token"),
  agentToken: document.querySelector("#agent-token"),
  connectionState: document.querySelector("#connection-state"),
  adminResults: document.querySelector("#admin-results"),
  adminResourceTitle: document.querySelector("#admin-resource-title"),
  adminResultCount: document.querySelector("#admin-result-count"),
  refreshAdmin: document.querySelector("#refresh-admin"),
  createAgentForm: document.querySelector("#create-agent-form"),
  registrationResult: document.querySelector("#registration-result"),
  sendMessageForm: document.querySelector("#send-message-form"),
  sendResult: document.querySelector("#send-result"),
  refreshInbox: document.querySelector("#refresh-inbox"),
  inboxResults: document.querySelector("#inbox-results"),
};

const RESOURCE_TITLES = {
  agents: "Agents",
  messages: "Messages",
  threads: "Threads",
  deliveries: "Deliveries",
  "audit-logs": "Audit logs",
};

const RESOURCE_PATHS = {
  agents: "/api/v1/admin/agents?limit=50",
  messages: "/api/v1/admin/messages?limit=50",
  threads: "/api/v1/admin/threads?limit=50",
  deliveries: "/api/v1/admin/deliveries?limit=50",
  "audit-logs": "/api/v1/admin/audit-logs?limit=50",
};

function requiredToken(input, label) {
  const token = input.value.trim();
  if (!token) {
    throw new Error(`请先填写 ${label}。`);
  }
  return token;
}

async function requestJson(path, options = {}) {
  const response = await fetch(path, {
    method: options.method || "GET",
    headers: options.headers || {},
    body: options.body,
    cache: "no-store",
    credentials: "same-origin",
    redirect: "error",
    referrerPolicy: "no-referrer",
  });

  let payload = null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    payload = await response.json();
  }
  if (!response.ok) {
    const error = new Error(errorMessage(payload, response.status));
    error.status = response.status;
    throw error;
  }
  return payload;
}

function errorMessage(payload, status) {
  const error = payload && typeof payload === "object" ? payload.error : null;
  if (error && typeof error === "object" && typeof error.message === "string") {
    return `请求失败 (${status})：${error.message}`;
  }
  return `请求失败 (${status})。`;
}

function bearer(token) {
  return { Authorization: `Bearer ${token}` };
}

function jsonHeaders(token) {
  return {
    ...bearer(token),
    "Content-Type": "application/json",
  };
}

function replaceChildrenWithStatus(container, message, kind = "muted") {
  const box = document.createElement("div");
  box.className = `empty-state ${kind}`;
  box.textContent = message;
  container.replaceChildren(box);
}

function setStatus(container, message, kind = "muted") {
  container.className = `status-box ${kind}`;
  container.textContent = message;
}

function setConnection(message, kind = "") {
  elements.connectionState.className = `health-pill ${kind}`.trim();
  elements.connectionState.textContent = message;
}

function listItems(payload) {
  if (Array.isArray(payload)) {
    return payload;
  }
  if (payload && typeof payload === "object" && Array.isArray(payload.items)) {
    return payload.items;
  }
  return payload === null ? [] : [payload];
}

function safeText(value, fallback = "—") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function prettyText(value) {
  if (typeof value === "string") {
    return value;
  }
  return JSON.stringify(value, null, 2);
}

function summaryFor(resource, item, index) {
  if (!item || typeof item !== "object") {
    return { title: `${RESOURCE_TITLES[resource]} ${index + 1}`, meta: "" };
  }
  if (resource === "agents") {
    return {
      title: safeText(item.address || item.display_name, `Agent ${index + 1}`),
      meta: `${safeText(item.status)} · ${safeText(item.id)}`,
    };
  }
  if (resource === "messages") {
    return {
      title: safeText(item.subject, "无主题消息"),
      meta: `${safeText(item.type || item.message_type)} · ${safeText(item.message_id || item.id)}`,
    };
  }
  if (resource === "threads") {
    return {
      title: `Thread ${safeText(item.thread_id || item.id)}`,
      meta: `${safeText(item.message_count, "0")} messages · last ${safeText(item.last_message_at)}`,
    };
  }
  if (resource === "deliveries") {
    return {
      title: `Delivery ${safeText(item.id || item.delivery_id)}`,
      meta: `${safeText(item.status || item.delivery_status)} · ${safeText(item.message_id)}`,
    };
  }
  return {
    title: safeText(item.action || item.event_type, `Audit event ${index + 1}`),
    meta: `${safeText(item.created_at)} · ${safeText(item.request_id)}`,
  };
}

function renderAdminResults(resource, payload) {
  const items = listItems(payload);
  elements.adminResults.replaceChildren();
  elements.adminResultCount.textContent = String(items.length);
  if (items.length === 0) {
    replaceChildrenWithStatus(elements.adminResults, "当前没有记录。");
    return;
  }

  const fragment = document.createDocumentFragment();
  items.forEach((item, index) => {
    const summary = summaryFor(resource, item, index);
    const card = document.createElement("article");
    card.className = "result-card";

    const heading = document.createElement("div");
    heading.className = "card-heading";
    const title = document.createElement("strong");
    title.textContent = summary.title;
    const chip = document.createElement("span");
    chip.className = "status-chip";
    chip.textContent = RESOURCE_TITLES[resource];
    heading.append(title, chip);

    const meta = document.createElement("div");
    meta.className = "card-meta";
    meta.textContent = summary.meta;

    const raw = document.createElement("pre");
    raw.textContent = prettyText(item);
    card.append(heading, meta, raw);
    fragment.append(card);
  });
  elements.adminResults.append(fragment);
}

async function refreshAdmin() {
  elements.refreshAdmin.disabled = true;
  replaceChildrenWithStatus(elements.adminResults, "正在查询…");
  try {
    const token = requiredToken(elements.adminToken, "Admin token");
    const payload = await requestJson(RESOURCE_PATHS[state.adminResource], {
      headers: bearer(token),
    });
    renderAdminResults(state.adminResource, payload);
    setConnection("管理接口已连接", "success");
  } catch (error) {
    replaceChildrenWithStatus(elements.adminResults, error.message, "error");
    elements.adminResultCount.textContent = "—";
    setConnection("请求失败", "error");
  } finally {
    elements.refreshAdmin.disabled = false;
  }
}

function selectResource(button) {
  const resource = button.dataset.resource;
  if (!Object.hasOwn(RESOURCE_TITLES, resource)) {
    return;
  }
  state.adminResource = resource;
  document.querySelectorAll(".tab[data-resource]").forEach((tab) => {
    const active = tab === button;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
  });
  elements.adminResourceTitle.textContent = RESOURCE_TITLES[resource];
  elements.adminResultCount.textContent = "—";
  replaceChildrenWithStatus(elements.adminResults, `点击“刷新当前视图”查询 ${RESOURCE_TITLES[resource]}。`);
}

function capabilitiesFromInput() {
  const values = document
    .querySelector("#agent-capabilities")
    .value.split(",")
    .map((value) => value.trim().toLowerCase())
    .filter(Boolean);
  return Array.from(new Set(values));
}

async function createAgent(event) {
  event.preventDefault();
  const submit = elements.createAgentForm.querySelector("button[type='submit']");
  submit.disabled = true;
  setStatus(elements.registrationResult, "正在创建 Agent…");
  try {
    const registrationToken = elements.registrationToken.value.trim();
    const displayName = document.querySelector("#agent-display-name").value.trim();
    const description = document.querySelector("#agent-description").value.trim();
    const payload = {
      address: document.querySelector("#agent-address").value.trim(),
      capabilities: capabilitiesFromInput(),
    };
    if (displayName) {
      payload.display_name = displayName;
    }
    if (description) {
      payload.description = description;
    }

    const registrationHeaders = { "Content-Type": "application/json" };
    if (registrationToken) {
      registrationHeaders["X-Registration-Token"] = registrationToken;
    }
    const result = await requestJson("/api/v1/agents", {
      method: "POST",
      headers: registrationHeaders,
      body: JSON.stringify(payload),
    });
    if (!result || typeof result.api_key !== "string" || !result.agent) {
      throw new Error("创建成功响应缺少 Agent identity 或一次性 API key。");
    }

    elements.agentToken.value = result.api_key;
    const address = safeText(result.agent.address, payload.address);
    const prefix = safeText(result.api_key_prefix, "已生成");
    setStatus(
      elements.registrationResult,
      `已创建 ${address}。API key (${prefix}…) 已放入 Agent 密码框；请按需安全保存。`,
      "success",
    );
  } catch (error) {
    setStatus(elements.registrationResult, error.message, "error");
  } finally {
    submit.disabled = false;
  }
}

function freshIdempotencyKey() {
  if (!globalThis.crypto || typeof globalThis.crypto.randomUUID !== "function") {
    throw new Error("当前浏览器无法生成安全随机幂等键。请使用支持 crypto.randomUUID 的安全上下文。");
  }
  return `ui_${globalThis.crypto.randomUUID()}`;
}

async function sendMessage(event) {
  event.preventDefault();
  const submit = elements.sendMessageForm.querySelector("button[type='submit']");
  submit.disabled = true;
  setStatus(elements.sendResult, "服务器正在接受消息…");
  try {
    const token = requiredToken(elements.agentToken, "Agent API key");
    const messageType = document.querySelector("#message-type").value;
    const body = document.querySelector("#message-body").value;
    const payload = {
      to: [{ address: document.querySelector("#message-to").value.trim() }],
      type: messageType,
      subject: document.querySelector("#message-subject").value,
      content: {
        format: document.querySelector("#message-format").value,
        body,
      },
      attachments: [],
      priority: "normal",
      requires_ack: true,
      metadata: { source: "agentpost_admin_debug_ui" },
      expires_at: null,
    };
    if (messageType === "task") {
      payload.task = { instruction: body };
    }

    const result = await requestJson("/api/v1/messages", {
      method: "POST",
      headers: {
        ...jsonHeaders(token),
        "Idempotency-Key": freshIdempotencyKey(),
      },
      body: JSON.stringify(payload),
    });
    setStatus(
      elements.sendResult,
      `消息已接受：${safeText(result && result.message_id)} · ${safeText(result && result.delivery && result.delivery.status)}`,
      "success",
    );
  } catch (error) {
    setStatus(elements.sendResult, error.message, "error");
  } finally {
    submit.disabled = false;
  }
}

function messageSender(message) {
  const sender = message && (message.from || message.sender);
  if (sender && typeof sender === "object") {
    return safeText(sender.address || sender.agent_id);
  }
  return safeText(sender);
}

function renderInbox(payload) {
  const messages = listItems(payload);
  elements.inboxResults.replaceChildren();
  if (messages.length === 0) {
    replaceChildrenWithStatus(elements.inboxResults, "Inbox 当前没有匹配消息。");
    return;
  }

  const fragment = document.createDocumentFragment();
  messages.forEach((message) => {
    const card = document.createElement("article");
    card.className = "message-card external-content";

    const heading = document.createElement("div");
    heading.className = "card-heading";
    const title = document.createElement("strong");
    title.textContent = safeText(message && message.subject, "无主题消息");
    const label = document.createElement("span");
    label.className = "external-label";
    label.textContent = "external_agent_content";
    heading.append(title, label);

    const meta = document.createElement("div");
    meta.className = "card-meta";
    const delivery = message && message.delivery;
    meta.textContent = `${messageSender(message)} · ${safeText(message && (message.type || message.message_type))} · ${safeText(delivery && delivery.status)} · ${safeText(message && message.message_id)}`;

    const body = document.createElement("pre");
    const content = message && message.content;
    body.textContent = prettyText(content && Object.hasOwn(content, "body") ? content.body : "");
    card.append(heading, meta, body);
    fragment.append(card);
  });
  elements.inboxResults.append(fragment);
}

async function refreshInbox() {
  elements.refreshInbox.disabled = true;
  replaceChildrenWithStatus(elements.inboxResults, "正在查询 Inbox…");
  try {
    const token = requiredToken(elements.agentToken, "Agent API key");
    const status = document.querySelector("#inbox-status").value;
    const path = status
      ? `/api/v1/inbox?status=${encodeURIComponent(status)}&limit=50`
      : "/api/v1/inbox?limit=50";
    const payload = await requestJson(path, { headers: bearer(token) });
    renderInbox(payload);
    setConnection("Agent Inbox 已连接", "success");
  } catch (error) {
    replaceChildrenWithStatus(elements.inboxResults, error.message, "error");
    setConnection("请求失败", "error");
  } finally {
    elements.refreshInbox.disabled = false;
  }
}

document.querySelectorAll(".tab[data-resource]").forEach((button) => {
  button.addEventListener("click", () => selectResource(button));
});
elements.refreshAdmin.addEventListener("click", refreshAdmin);
elements.createAgentForm.addEventListener("submit", createAgent);
elements.sendMessageForm.addEventListener("submit", sendMessage);
elements.refreshInbox.addEventListener("click", refreshInbox);

window.addEventListener("pagehide", () => {
  elements.adminToken.value = "";
  elements.registrationToken.value = "";
  elements.agentToken.value = "";
});

replaceChildrenWithStatus(elements.adminResults, "填写 Admin token 后刷新 Agents。 ");
replaceChildrenWithStatus(elements.inboxResults, "填写 Agent API key 后查询 Inbox。");
