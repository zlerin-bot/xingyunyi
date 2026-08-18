"use strict";

const state = {
  dashboard: null,
  csrfToken: "",
  pairingRequestSignature: "",
  pairingIdempotencyKey: "",
  requestedPairingOpened: false,
  authConfig: null,
  registerChallengeId: "",
  recoveryChallengeId: "",
  mfaSetupStarted: false,
};

const elements = {
  welcomeView: document.querySelector("#welcome-view"),
  workspaceView: document.querySelector("#workspace-view"),
  accessForm: document.querySelector("#access-form"),
  accessKey: document.querySelector("#human-access-key"),
  loginForm: document.querySelector("#login-form"),
  loginEmail: document.querySelector("#login-email"),
  loginPassword: document.querySelector("#login-password"),
  loginMfa: document.querySelector("#login-mfa"),
  openRegister: document.querySelector("#open-register"),
  openRecovery: document.querySelector("#open-recovery"),
  legacyEntry: document.querySelector("#legacy-entry"),
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
  metricApprovals: document.querySelector("#metric-approvals"),
  organizationCount: document.querySelector("#organization-count"),
  organizationList: document.querySelector("#organization-list"),
  agentCount: document.querySelector("#agent-count"),
  agentList: document.querySelector("#agent-list"),
  taskList: document.querySelector("#task-list"),
  approvalList: document.querySelector("#approval-list"),
  messageList: document.querySelector("#message-list"),
  connectorList: document.querySelector("#connector-list"),
  securityStatus: document.querySelector("#security-status"),
  openMfa: document.querySelector("#open-mfa"),
  openKeyRotation: document.querySelector("#open-key-rotation"),
  openPairing: document.querySelector("#open-pairing"),
  approvalDialog: document.querySelector("#approval-dialog"),
  approvalForm: document.querySelector("#approval-form"),
  approvalDialogTitle: document.querySelector("#approval-dialog-title"),
  approvalDialogSummary: document.querySelector("#approval-dialog-summary"),
  approvalId: document.querySelector("#approval-id"),
  approvalDecision: document.querySelector("#approval-decision"),
  approvalNote: document.querySelector("#approval-note"),
  approvalAccessKey: document.querySelector("#approval-access-key"),
  approvalMfa: document.querySelector("#approval-mfa"),
  approvalResult: document.querySelector("#approval-result"),
  approvalSubmit: document.querySelector("#approval-submit"),
  approvalClose: document.querySelector("#approval-close"),
  approvalCancel: document.querySelector("#approval-cancel"),
  pairingDialog: document.querySelector("#pairing-dialog"),
  pairingForm: document.querySelector("#pairing-form"),
  pairingClose: document.querySelector("#pairing-close"),
  pairingCancel: document.querySelector("#pairing-cancel"),
  pairingDeny: document.querySelector("#pairing-deny"),
  pairingSubmit: document.querySelector("#pairing-submit"),
  pairingId: document.querySelector("#pairing-id"),
  pairingUserCode: document.querySelector("#pairing-user-code"),
  pairingLocalId: document.querySelector("#pairing-local-id"),
  pairingDisplayName: document.querySelector("#pairing-display-name"),
  pairingCapabilities: document.querySelector("#pairing-capabilities"),
  pairingAccessKey: document.querySelector("#pairing-access-key"),
  pairingMfa: document.querySelector("#pairing-mfa"),
  pairingPreview: document.querySelector("#pairing-preview"),
  pairingResult: document.querySelector("#pairing-result"),
  revokeDialog: document.querySelector("#revoke-dialog"),
  revokeForm: document.querySelector("#revoke-form"),
  revokeClose: document.querySelector("#revoke-close"),
  revokeCancel: document.querySelector("#revoke-cancel"),
  revokeSubmit: document.querySelector("#revoke-submit"),
  revokeConnectorId: document.querySelector("#revoke-connector-id"),
  revokeAccessKey: document.querySelector("#revoke-access-key"),
  revokeMfa: document.querySelector("#revoke-mfa"),
  revokeSummary: document.querySelector("#revoke-summary"),
  revokeResult: document.querySelector("#revoke-result"),
  registerDialog: document.querySelector("#register-dialog"),
  registerForm: document.querySelector("#register-form"),
  registerClose: document.querySelector("#register-close"),
  registerCancel: document.querySelector("#register-cancel"),
  registerEmail: document.querySelector("#register-email"),
  registerCode: document.querySelector("#register-code"),
  registerName: document.querySelector("#register-name"),
  registerPassword: document.querySelector("#register-password"),
  registerSendCode: document.querySelector("#register-send-code"),
  registerResult: document.querySelector("#register-result"),
  recoveryDialog: document.querySelector("#recovery-dialog"),
  recoveryForm: document.querySelector("#recovery-form"),
  recoveryClose: document.querySelector("#recovery-close"),
  recoveryCancel: document.querySelector("#recovery-cancel"),
  recoveryEmail: document.querySelector("#recovery-email"),
  recoveryCode: document.querySelector("#recovery-code"),
  recoveryPassword: document.querySelector("#recovery-password"),
  recoveryMfa: document.querySelector("#recovery-mfa"),
  recoverySendCode: document.querySelector("#recovery-send-code"),
  recoveryResult: document.querySelector("#recovery-result"),
  mfaDialog: document.querySelector("#mfa-dialog"),
  mfaForm: document.querySelector("#mfa-form"),
  mfaClose: document.querySelector("#mfa-close"),
  mfaCancel: document.querySelector("#mfa-cancel"),
  mfaCreate: document.querySelector("#mfa-create"),
  mfaPassword: document.querySelector("#mfa-password"),
  mfaCurrentProof: document.querySelector("#mfa-current-proof"),
  mfaConfirmCode: document.querySelector("#mfa-confirm-code"),
  mfaProvisioning: document.querySelector("#mfa-provisioning"),
  mfaResult: document.querySelector("#mfa-result"),
  keyDialog: document.querySelector("#key-dialog"),
  keyForm: document.querySelector("#key-form"),
  keyClose: document.querySelector("#key-close"),
  keyCancel: document.querySelector("#key-cancel"),
  keyPassword: document.querySelector("#key-password"),
  keyMfa: document.querySelector("#key-mfa"),
  keyLabel: document.querySelector("#key-label"),
  keyOutput: document.querySelector("#key-output"),
  keyResult: document.querySelector("#key-result"),
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

function errorMessage(payload, status) {
  const error = payload && typeof payload === "object" ? payload.error : null;
  if (error && typeof error.message === "string") {
    return `星轨请求失败（${status}）：${error.message}`;
  }
  return `星轨请求失败（${status}）。`;
}

async function requestJson(path, options = {}) {
  const response = await fetch(path, {
    method: options.method || "GET",
    headers: options.headers || {},
    cache: "no-store",
    credentials: "same-origin",
    redirect: "error",
    referrerPolicy: "no-referrer",
    body: options.body,
  });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    const error = new Error(errorMessage(payload, response.status));
    error.status = response.status;
    throw error;
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

function mfaProof(value) {
  const candidate = value.trim();
  if (!candidate) {
    return { totp_code: null, recovery_code: null };
  }
  if (/^[0-9]{6}$/.test(candidate)) {
    return { totp_code: candidate, recovery_code: null };
  }
  return { totp_code: null, recovery_code: candidate };
}

function reauthentication(candidate, mfaValue, extra = {}) {
  const headers = {
    "Content-Type": "application/json",
    "X-CSRF-Token": state.csrfToken,
  };
  const payload = { ...extra, ...mfaProof(mfaValue) };
  if (candidate.startsWith("hum_")) {
    headers.Authorization = `Bearer ${candidate}`;
  } else {
    payload.password = candidate;
  }
  return { headers, payload };
}

function validReauthenticationCandidate(candidate) {
  return candidate.startsWith("hum_") ? candidate.length >= 20 : candidate.length >= 12;
}

function clearSensitiveInputs() {
  [
    elements.accessKey,
    elements.loginPassword,
    elements.loginMfa,
    elements.registerCode,
    elements.registerPassword,
    elements.recoveryCode,
    elements.recoveryPassword,
    elements.recoveryMfa,
    elements.mfaPassword,
    elements.mfaCurrentProof,
    elements.mfaConfirmCode,
    elements.keyPassword,
    elements.keyMfa,
    elements.approvalAccessKey,
    elements.approvalMfa,
    elements.pairingAccessKey,
    elements.pairingMfa,
    elements.revokeAccessKey,
    elements.revokeMfa,
  ].forEach((input) => {
    if (input) {
      input.value = "";
    }
  });
  elements.mfaProvisioning.textContent = "";
  elements.mfaProvisioning.hidden = true;
  elements.keyOutput.textContent = "";
  elements.keyOutput.hidden = true;
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
    approved: "已批准",
    rejected: "已拒绝",
    expired: "已过期",
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
    admin: "组织管理员",
    member: "组织成员",
    consumed: "已领取",
    denied: "已拒绝",
    revoked: "已撤销",
    replaced: "已替换",
  };
  return labels[value] || safeText(value);
}

function chip(value, type = "status") {
  const item = document.createElement("span");
  item.className = `data-chip ${type} ${safeText(value, "unknown")}`;
  item.textContent = statusLabel(value);
  return item;
}

function renderMetrics(metrics, agents, organizations) {
  elements.metricAgents.textContent = safeText(metrics.agent_count, "0");
  elements.metricUnread.textContent = safeText(metrics.unread_delivery_count, "0");
  elements.metricPending.textContent = safeText(metrics.pending_task_count, "0");
  elements.metricOnline.textContent = safeText(metrics.online_recently_count, "0");
  elements.metricApprovals.textContent = safeText(metrics.pending_approval_count, "0");
  const active = agents.filter((agent) => agent.status === "active").length;
  elements.overviewCopy.textContent = `当前进入 ${organizations.length} 个组织治理范围，可观察 ${agents.length} 个 Agent，其中 ${active} 个身份处于 active；通信状态和工作状态仍分别呈现。`;
}

function renderOrganizations(organizations) {
  elements.organizationList.replaceChildren();
  elements.organizationCount.textContent = `${organizations.length} 个`;
  if (organizations.length === 0) {
    elements.organizationList.append(emptyState("尚未加入组织。个人直接授权的 Agent 仍会显示在“我的 Agent”中。"));
    return;
  }
  const fragment = document.createDocumentFragment();
  organizations.forEach((organization) => {
    const card = document.createElement("article");
    card.className = "organization-card";

    const header = document.createElement("div");
    header.className = "organization-heading";
    const identity = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = safeText(organization.name, organization.slug);
    const slug = document.createElement("span");
    slug.textContent = safeText(organization.slug);
    identity.append(name, slug);
    header.append(identity, chip(organization.membership_role, "role"));

    const description = document.createElement("p");
    description.textContent = safeText(organization.description, "该组织暂未填写说明。");

    const stats = document.createElement("dl");
    [["成员", organization.member_count], ["Agent", organization.agent_count]].forEach(([label, value]) => {
      const cell = document.createElement("div");
      const term = document.createElement("dt");
      term.textContent = label;
      const detail = document.createElement("dd");
      detail.textContent = safeText(value, "0");
      cell.append(term, detail);
      stats.append(cell);
    });
    card.append(header, description, stats);
    fragment.append(card);
  });
  elements.organizationList.append(fragment);
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
    card.append(top);
    if (agent.organization) {
      const organization = document.createElement("div");
      organization.className = "agent-organization";
      organization.textContent = `${safeText(agent.organization.name)} · ${agent.access_source === "organization" ? "组织授权" : "直接授权"}`;
      card.append(organization);
    }
    card.append(capabilities, stats);
    fragment.append(card);
  });
  elements.agentList.append(fragment);
}

function openRevokeDialog(connector) {
  elements.revokeConnectorId.value = safeText(connector.connector_id, "");
  elements.revokeSummary.textContent = `将撤销 ${safeText(connector.agent?.address)} 当前使用的 ${safeText(connector.display_name)} 连接。`;
  elements.revokeResult.textContent = "请重新输入当前密码（或兼容 Human Key）；凭证验证后立即清除。";
  elements.revokeResult.className = "form-status";
  elements.revokeDialog.showModal();
  elements.revokeAccessKey.focus();
}

function renderConnectors(connectors) {
  elements.connectorList.replaceChildren();
  if (!connectors.length) {
    elements.connectorList.append(emptyState("尚未通过星轨连接 Agent。点击“连接 Agent”并使用本地 Connector 生成的一次性配对信息。"));
    return;
  }
  const fragment = document.createDocumentFragment();
  connectors.forEach((connector) => {
    const card = document.createElement("article");
    card.className = "connector-card";
    const heading = document.createElement("div");
    heading.className = "connector-heading";
    const identity = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = safeText(connector.display_name, connector.connector_type);
    const address = document.createElement("span");
    address.textContent = safeText(connector.agent?.address);
    identity.append(name, address);
    heading.append(identity, chip(connector.status));

    const facts = document.createElement("dl");
    [
      ["宿主", connector.connector_type],
      ["设备", connector.device_name],
      ["版本", connector.client_version],
      ["最近连接", dateText(connector.last_seen_at)],
    ].forEach(([label, value]) => {
      const cell = document.createElement("div");
      const term = document.createElement("dt");
      term.textContent = label;
      const detail = document.createElement("dd");
      detail.textContent = safeText(value);
      cell.append(term, detail);
      facts.append(cell);
    });
    card.append(heading, facts);
    if (connector.is_current && connector.status === "active") {
      const actions = document.createElement("div");
      actions.className = "connector-actions";
      const current = document.createElement("span");
      current.textContent = "当前 Connector · Agent 身份与 Inbox 独立保留";
      const revoke = document.createElement("button");
      revoke.type = "button";
      revoke.className = "quiet-button danger";
      revoke.textContent = "撤销连接";
      revoke.addEventListener("click", () => openRevokeDialog(connector));
      actions.append(current, revoke);
      card.append(actions);
    }
    fragment.append(card);
  });
  elements.connectorList.append(fragment);
}

function closePairingDialog({ clear = true } = {}) {
  elements.pairingAccessKey.value = "";
  elements.pairingMfa.value = "";
  elements.pairingResult.textContent = "";
  if (clear) {
    elements.pairingId.value = "";
    elements.pairingUserCode.value = "";
    elements.pairingLocalId.value = "";
    elements.pairingDisplayName.value = "";
    elements.pairingCapabilities.value = "";
    elements.pairingPreview.replaceChildren();
    elements.pairingPreview.hidden = true;
    state.pairingRequestSignature = "";
    state.pairingIdempotencyKey = "";
  }
  if (elements.pairingDialog.open) {
    elements.pairingDialog.close();
  }
}

function renderPairingPreview(pairing) {
  elements.pairingPreview.replaceChildren();
  const heading = document.createElement("strong");
  heading.textContent = safeText(pairing.connector_display_name, pairing.connector_type);
  const details = document.createElement("p");
  details.textContent = `${safeText(pairing.connector_type)} · ${safeText(pairing.device_name, "未声明设备")} · ${safeText(pairing.client_version, "未声明版本")}`;
  const capabilities = document.createElement("p");
  const values = Array.isArray(pairing.requested_capabilities) ? pairing.requested_capabilities : [];
  capabilities.textContent = `自声明能力：${values.length ? values.join("、") : "无"}`;
  const warning = document.createElement("span");
  warning.textContent = `校验尾码 ${safeText(pairing.user_code_hint)} · ${statusLabel(pairing.status)}`;
  elements.pairingPreview.append(heading, details, capabilities, warning);
  elements.pairingPreview.hidden = false;
}

async function loadPairingPreview() {
  const pairingId = elements.pairingId.value.trim();
  if (!pairingId.startsWith("pair_")) {
    elements.pairingPreview.hidden = true;
    return;
  }
  try {
    const pairing = await requestJson(`/api/v1/orbit/pairings/${encodeURIComponent(pairingId)}`);
    renderPairingPreview(pairing);
    elements.pairingResult.textContent = "请核对本地 Connector 展示的完整配对码和以上设备信息。";
    elements.pairingResult.className = "form-status";
  } catch (error) {
    elements.pairingPreview.hidden = true;
    elements.pairingResult.textContent = error.message;
    elements.pairingResult.className = "form-status error";
  }
}

async function openPairingDialog(pairingId = "", userCode = "") {
  elements.pairingId.value = pairingId;
  elements.pairingUserCode.value = userCode;
  elements.pairingResult.textContent = "长期凭证不会进入浏览器；批准后由发起配对的 Connector 自动领取。";
  elements.pairingResult.className = "form-status";
  elements.pairingDialog.showModal();
  if (pairingId) {
    await loadPairingPreview();
  }
  (pairingId ? elements.pairingLocalId : elements.pairingId).focus();
}

function pairingPayload(decision) {
  if (decision === "denied") {
    return { decision: "denied" };
  }
  const capabilities = [...new Set(
    elements.pairingCapabilities.value
      .split(",")
      .map((value) => value.trim().toLowerCase())
      .filter(Boolean),
  )];
  return {
    decision: "approved",
    local_agent_id: elements.pairingLocalId.value.trim().toLowerCase(),
    display_name: elements.pairingDisplayName.value.trim() || null,
    capabilities: capabilities.length ? capabilities : null,
  };
}

function pairingIdempotencyKey(pairingId, payload) {
  const signature = JSON.stringify({ pairingId, payload });
  if (signature !== state.pairingRequestSignature) {
    state.pairingRequestSignature = signature;
    state.pairingIdempotencyKey = `xinggui-pairing-${crypto.randomUUID()}`;
  }
  return state.pairingIdempotencyKey;
}

async function decidePairing(event, forcedDecision = null) {
  event.preventDefault();
  const decision = forcedDecision || "approved";
  const pairingId = elements.pairingId.value.trim();
  const userCode = elements.pairingUserCode.value.trim();
  const humanKey = elements.pairingAccessKey.value.trim();
  const mfa = elements.pairingMfa.value.trim();
  const payload = pairingPayload(decision);
  if (!state.csrfToken || !pairingId.startsWith("pair_") || !userCode || !validReauthenticationCandidate(humanKey)) {
    elements.pairingResult.textContent = "请填写有效的配对 ID、一次性配对码和当前密码（或兼容 Human Key）。";
    elements.pairingResult.className = "form-status error";
    return;
  }
  if (decision === "approved" && !payload.local_agent_id) {
    elements.pairingResult.textContent = "请填写 Agent 地址前缀。";
    elements.pairingResult.className = "form-status error";
    return;
  }
  elements.pairingSubmit.disabled = true;
  elements.pairingDeny.disabled = true;
  elements.pairingResult.textContent = "正在验证配对码和 Human 身份…";
  elements.pairingResult.className = "form-status";
  try {
    let confirmation;
    try {
      const proof = reauthentication(humanKey, mfa, {
        intent: decision === "approved" ? "approve" : "deny",
        user_code: userCode,
      });
      confirmation = await requestJson(
        `/api/v1/orbit/pairings/${encodeURIComponent(pairingId)}/confirmation`,
        {
          method: "POST",
          headers: proof.headers,
          body: JSON.stringify(proof.payload),
        },
      );
    } finally {
      elements.pairingAccessKey.value = "";
      elements.pairingMfa.value = "";
    }
    elements.pairingResult.textContent = decision === "approved"
      ? "身份已确认，正在创建 Agent 身份与当前 Connector…"
      : "身份已确认，正在拒绝本次配对…";
    await requestJson(`/api/v1/orbit/pairings/${encodeURIComponent(pairingId)}/decision`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": pairingIdempotencyKey(pairingId, payload),
        "X-CSRF-Token": state.csrfToken,
        "X-Human-Confirmation": confirmation.confirmation_token,
      },
      body: JSON.stringify(payload),
    });
    closePairingDialog();
    history.replaceState(null, "", "/orbit");
    await loadDashboard();
    setConnection(
      decision === "approved" ? "Agent 已加入云驿，等待 Connector 领取凭证" : "配对已拒绝",
      "success",
    );
  } catch (error) {
    elements.pairingAccessKey.value = "";
    elements.pairingMfa.value = "";
    elements.pairingResult.textContent = error.message;
    elements.pairingResult.className = "form-status error";
  } finally {
    elements.pairingSubmit.disabled = false;
    elements.pairingDeny.disabled = false;
  }
}

function closeRevokeDialog() {
  elements.revokeAccessKey.value = "";
  elements.revokeMfa.value = "";
  elements.revokeConnectorId.value = "";
  elements.revokeResult.textContent = "";
  if (elements.revokeDialog.open) {
    elements.revokeDialog.close();
  }
}

async function revokeConnector(event) {
  event.preventDefault();
  const connectorId = elements.revokeConnectorId.value.trim();
  const humanKey = elements.revokeAccessKey.value.trim();
  const mfa = elements.revokeMfa.value.trim();
  if (!state.csrfToken || !connectorId.startsWith("con_") || !validReauthenticationCandidate(humanKey)) {
    elements.revokeResult.textContent = "请重新输入当前密码（或兼容 Human Key）。";
    elements.revokeResult.className = "form-status error";
    return;
  }
  elements.revokeSubmit.disabled = true;
  try {
    let confirmation;
    try {
      const proof = reauthentication(humanKey, mfa);
      confirmation = await requestJson(
        `/api/v1/orbit/connectors/${encodeURIComponent(connectorId)}/confirmation`,
        {
          method: "POST",
          headers: proof.headers,
          body: JSON.stringify(proof.payload),
        },
      );
    } finally {
      elements.revokeAccessKey.value = "";
      elements.revokeMfa.value = "";
    }
    await requestJson(`/api/v1/orbit/connectors/${encodeURIComponent(connectorId)}`, {
      method: "DELETE",
      headers: {
        "X-CSRF-Token": state.csrfToken,
        "X-Human-Confirmation": confirmation.confirmation_token,
      },
    });
    closeRevokeDialog();
    await loadDashboard();
    setConnection("Connector 已撤销；Agent 身份与 Inbox 已保留", "success");
  } catch (error) {
    elements.revokeResult.textContent = error.message;
    elements.revokeResult.className = "form-status error";
  } finally {
    elements.revokeSubmit.disabled = false;
  }
}

async function maybeOpenRequestedPairing() {
  if (state.requestedPairingOpened) {
    return;
  }
  const parameters = new URLSearchParams(window.location.search);
  const pairingId = parameters.get("pairing") || "";
  const userCode = parameters.get("code") || "";
  if (!pairingId) {
    return;
  }
  state.requestedPairingOpened = true;
  await openPairingDialog(pairingId, userCode);
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

function closeApprovalDialog() {
  elements.approvalAccessKey.value = "";
  elements.approvalMfa.value = "";
  elements.approvalNote.value = "";
  elements.approvalResult.textContent = "";
  elements.approvalId.value = "";
  elements.approvalDecision.value = "";
  if (elements.approvalDialog.open) {
    elements.approvalDialog.close();
  }
}

function openApprovalDialog(approval, decision) {
  elements.approvalId.value = safeText(approval.approval_id, "");
  elements.approvalDecision.value = decision;
  elements.approvalDialogTitle.textContent = decision === "approved" ? "批准这项申请" : "拒绝这项申请";
  elements.approvalDialogSummary.textContent = safeText(
    approval.summary,
    "申请内容因审计角色而隐藏。",
  );
  elements.approvalSubmit.textContent = decision === "approved" ? "确认批准" : "确认拒绝";
  elements.approvalResult.textContent = "请重新输入当前密码（或兼容 Human Key）；凭证验证后立即清除。";
  elements.approvalDialog.showModal();
  elements.approvalAccessKey.focus();
}

function renderApprovals(approvals) {
  elements.approvalList.replaceChildren();
  if (!approvals.length) {
    elements.approvalList.append(emptyState("当前没有你可见的 Agent 审批申请。"));
    return;
  }
  const fragment = document.createDocumentFragment();
  approvals.forEach((approval) => {
    const card = document.createElement("article");
    card.className = "approval-card";
    const heading = document.createElement("div");
    heading.className = "approval-heading";
    const identity = document.createElement("div");
    const type = document.createElement("span");
    type.className = "approval-action-type";
    type.textContent = safeText(approval.action_type);
    const title = document.createElement("strong");
    title.textContent = safeText(approval.requester_address);
    identity.append(type, title);
    heading.append(identity, chip(approval.status));

    const summary = document.createElement("p");
    summary.className = "approval-summary";
    summary.textContent = approval.content_redacted
      ? "申请内容因审计角色而隐藏。"
      : safeText(approval.summary, "无申请摘要");
    const justification = document.createElement("p");
    justification.className = "approval-justification";
    justification.textContent = approval.content_redacted
      ? "理由与参数不可见。"
      : safeText(approval.justification, "Agent 未提供额外理由。");
    const payload = document.createElement("pre");
    payload.className = "approval-payload";
    payload.textContent = approval.content_redacted
      ? "external_agent_content · redacted"
      : safeText(approval.payload, "{}");
    const metadata = document.createElement("div");
    metadata.className = "approval-meta";
    [
      `风险：${safeText(approval.risk_level)}`,
      `角色：${statusLabel(approval.access_role)}`,
      `申请：${dateText(approval.created_at)}`,
      `到期：${dateText(approval.expires_at)}`,
    ].forEach((value) => {
      const item = document.createElement("span");
      item.textContent = value;
      metadata.append(item);
    });
    card.append(heading, summary, justification, payload, metadata);

    if (approval.status === "pending" && approval.can_decide) {
      const actions = document.createElement("div");
      actions.className = "approval-actions";
      const reject = document.createElement("button");
      reject.type = "button";
      reject.className = "approval-action reject";
      reject.textContent = "拒绝";
      reject.addEventListener("click", () => openApprovalDialog(approval, "rejected"));
      const approve = document.createElement("button");
      approve.type = "button";
      approve.className = "approval-action approve";
      approve.textContent = "批准";
      approve.addEventListener("click", () => openApprovalDialog(approval, "approved"));
      actions.append(reject, approve);
      card.append(actions);
    }
    fragment.append(card);
  });
  elements.approvalList.append(fragment);
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

function renderSecurity(security) {
  const password = security.password_configured ? "密码已设置" : "需先找回账户设置密码";
  const mfa = security.mfa_enabled ? "MFA 已启用" : "MFA 未启用";
  const keys = `${safeText(security.active_human_keys, "0")} 个兼容 Key`;
  elements.securityStatus.textContent = `${password} · ${mfa} · ${keys}`;
  elements.openMfa.disabled = !security.password_configured;
  elements.openKeyRotation.disabled = !security.password_configured;
}

function renderDashboard(dashboard) {
  state.dashboard = dashboard;
  const user = dashboard.user || {};
  const organizations = Array.isArray(dashboard.organizations) ? dashboard.organizations : [];
  const agents = Array.isArray(dashboard.agents) ? dashboard.agents : [];
  const tasks = Array.isArray(dashboard.tasks) ? dashboard.tasks : [];
  const approvals = Array.isArray(dashboard.approvals) ? dashboard.approvals : [];
  const messages = Array.isArray(dashboard.recent_messages) ? dashboard.recent_messages : [];
  elements.humanName.textContent = safeText(user.display_name, "星轨用户");
  elements.humanEmail.textContent = safeText(user.email);
  elements.humanAvatar.textContent = safeText(user.display_name, "星").slice(0, 1);
  renderMetrics(dashboard.metrics || {}, agents, organizations);
  renderOrganizations(organizations);
  renderAgents(agents);
  renderTasks(tasks);
  renderApprovals(approvals);
  renderMessages(messages);
}

async function loadDashboard() {
  elements.refresh.disabled = true;
  setConnection("正在同步星轨", "loading");
  try {
    const [dashboard, connectors, security] = await Promise.all([
      requestJson("/api/v1/orbit/dashboard"),
      requestJson("/api/v1/orbit/connectors"),
      requestJson("/api/v1/orbit/security"),
    ]);
    renderDashboard(dashboard);
    renderConnectors(Array.isArray(connectors.items) ? connectors.items : []);
    renderSecurity(security);
    elements.welcomeView.hidden = true;
    elements.workspaceView.hidden = false;
    setConnection("星轨已连接", "success");
    await maybeOpenRequestedPairing();
  } catch (error) {
    setConnection("星轨连接失败", "error");
    throw error;
  } finally {
    elements.refresh.disabled = false;
  }
}

async function loadAuthConfig() {
  try {
    state.authConfig = await requestJson("/api/v1/auth/config");
  } catch (_error) {
    state.authConfig = { self_service_enabled: false, open_registration_enabled: false };
  }
  const selfService = Boolean(state.authConfig.self_service_enabled);
  elements.loginForm.hidden = !selfService;
  elements.openRecovery.hidden = !selfService;
  elements.openRegister.hidden = !Boolean(state.authConfig.open_registration_enabled);
  elements.legacyEntry.open = !selfService;
}

async function loginHuman(event) {
  event.preventDefault();
  const submit = elements.loginForm.querySelector("button[type='submit']");
  const email = elements.loginEmail.value.trim();
  const password = elements.loginPassword.value;
  const proof = mfaProof(elements.loginMfa.value);
  submit.disabled = true;
  setFormStatus("正在验证邮箱、密码和 MFA…");
  try {
    const browserSession = await requestJson("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, ...proof }),
    });
    state.csrfToken = browserSession.csrf_token;
    elements.loginPassword.value = "";
    elements.loginMfa.value = "";
    await loadDashboard();
    setFormStatus("身份验证成功，敏感输入已从页面清除。", "success");
  } catch (error) {
    setFormStatus(error.message, "error");
  } finally {
    elements.loginPassword.value = "";
    elements.loginMfa.value = "";
    submit.disabled = false;
  }
}

function closeRegisterDialog() {
  elements.registerCode.value = "";
  elements.registerPassword.value = "";
  elements.registerResult.textContent = "";
  state.registerChallengeId = "";
  if (elements.registerDialog.open) {
    elements.registerDialog.close();
  }
}

function closeRecoveryDialog() {
  elements.recoveryCode.value = "";
  elements.recoveryPassword.value = "";
  elements.recoveryMfa.value = "";
  elements.recoveryResult.textContent = "";
  state.recoveryChallengeId = "";
  if (elements.recoveryDialog.open) {
    elements.recoveryDialog.close();
  }
}

async function sendEmailChallenge(purpose) {
  const isRegister = purpose === "register";
  const emailInput = isRegister ? elements.registerEmail : elements.recoveryEmail;
  const codeInput = isRegister ? elements.registerCode : elements.recoveryCode;
  const result = isRegister ? elements.registerResult : elements.recoveryResult;
  const button = isRegister ? elements.registerSendCode : elements.recoverySendCode;
  button.disabled = true;
  result.textContent = "正在发送邮箱验证码…";
  result.className = "form-status";
  try {
    const challenge = await requestJson("/api/v1/auth/email/challenges", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: emailInput.value.trim(), purpose }),
    });
    if (isRegister) {
      state.registerChallengeId = challenge.challenge_id;
    } else {
      state.recoveryChallengeId = challenge.challenge_id;
    }
    if (challenge.test_verification_code) {
      codeInput.value = challenge.test_verification_code;
      result.textContent = "本地测试模式：验证码已填入；生产环境只通过邮件发送。";
    } else {
      result.textContent = "验证码已发送，请检查邮箱。";
    }
    result.className = "form-status success";
    codeInput.focus();
  } catch (error) {
    result.textContent = error.message;
    result.className = "form-status error";
  } finally {
    button.disabled = false;
  }
}

async function registerHuman(event) {
  event.preventDefault();
  if (!state.registerChallengeId) {
    elements.registerResult.textContent = "请先获取邮箱验证码。";
    elements.registerResult.className = "form-status error";
    return;
  }
  const submit = elements.registerForm.querySelector("button[type='submit']");
  submit.disabled = true;
  try {
    const browserSession = await requestJson("/api/v1/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        challenge_id: state.registerChallengeId,
        code: elements.registerCode.value.trim(),
        display_name: elements.registerName.value.trim(),
        password: elements.registerPassword.value,
      }),
    });
    state.csrfToken = browserSession.csrf_token;
    closeRegisterDialog();
    await loadDashboard();
    setFormStatus("账户已创建。建议现在启用 MFA。", "success");
  } catch (error) {
    elements.registerResult.textContent = error.message;
    elements.registerResult.className = "form-status error";
  } finally {
    elements.registerCode.value = "";
    elements.registerPassword.value = "";
    submit.disabled = false;
  }
}

async function recoverHuman(event) {
  event.preventDefault();
  if (!state.recoveryChallengeId) {
    elements.recoveryResult.textContent = "请先获取邮箱验证码。";
    elements.recoveryResult.className = "form-status error";
    return;
  }
  const submit = elements.recoveryForm.querySelector("button[type='submit']");
  submit.disabled = true;
  try {
    const browserSession = await requestJson("/api/v1/auth/recover", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        challenge_id: state.recoveryChallengeId,
        code: elements.recoveryCode.value.trim(),
        new_password: elements.recoveryPassword.value,
        ...mfaProof(elements.recoveryMfa.value),
      }),
    });
    state.csrfToken = browserSession.csrf_token;
    closeRecoveryDialog();
    await loadDashboard();
    setFormStatus("密码已重设，旧会话与兼容 Human Key 已撤销。", "success");
  } catch (error) {
    elements.recoveryResult.textContent = error.message;
    elements.recoveryResult.className = "form-status error";
  } finally {
    elements.recoveryCode.value = "";
    elements.recoveryPassword.value = "";
    elements.recoveryMfa.value = "";
    submit.disabled = false;
  }
}

function closeMfaDialog() {
  elements.mfaPassword.value = "";
  elements.mfaCurrentProof.value = "";
  elements.mfaConfirmCode.value = "";
  elements.mfaProvisioning.textContent = "";
  elements.mfaProvisioning.hidden = true;
  elements.mfaResult.textContent = "";
  state.mfaSetupStarted = false;
  if (elements.mfaDialog.open) {
    elements.mfaDialog.close();
  }
}

async function startMfaSetup() {
  if (!state.csrfToken || elements.mfaPassword.value.length < 12) {
    elements.mfaResult.textContent = "请输入当前密码。";
    elements.mfaResult.className = "form-status error";
    return;
  }
  elements.mfaCreate.disabled = true;
  try {
    const setup = await requestJson("/api/v1/orbit/security/totp/setup", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": state.csrfToken },
      body: JSON.stringify({
        password: elements.mfaPassword.value,
        ...mfaProof(elements.mfaCurrentProof.value),
      }),
    });
    state.mfaSetupStarted = true;
    elements.mfaProvisioning.hidden = false;
    elements.mfaProvisioning.textContent = `手工密钥：${setup.secret}\n认证器 URI：${setup.provisioning_uri}`;
    elements.mfaResult.textContent = "请将密钥加入认证器，再输入一枚新的 6 位动态码。";
    elements.mfaResult.className = "form-status success";
    elements.mfaConfirmCode.focus();
  } catch (error) {
    elements.mfaResult.textContent = error.message;
    elements.mfaResult.className = "form-status error";
  } finally {
    elements.mfaPassword.value = "";
    elements.mfaCurrentProof.value = "";
    elements.mfaCreate.disabled = false;
  }
}

async function confirmMfaSetup(event) {
  event.preventDefault();
  if (!state.mfaSetupStarted) {
    elements.mfaResult.textContent = "请先生成认证器密钥。";
    elements.mfaResult.className = "form-status error";
    return;
  }
  const submit = elements.mfaForm.querySelector("button[type='submit']");
  submit.disabled = true;
  try {
    const enabled = await requestJson("/api/v1/orbit/security/totp/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": state.csrfToken },
      body: JSON.stringify({ code: elements.mfaConfirmCode.value.trim() }),
    });
    elements.mfaProvisioning.textContent = `恢复码（仅显示一次，请离线保存）：\n${enabled.recovery_codes.join("\n")}`;
    elements.mfaResult.textContent = "MFA 已启用。保存恢复码后再关闭窗口。";
    elements.mfaResult.className = "form-status success";
    state.mfaSetupStarted = false;
    elements.mfaConfirmCode.value = "";
    await loadDashboard();
  } catch (error) {
    elements.mfaResult.textContent = error.message;
    elements.mfaResult.className = "form-status error";
  } finally {
    elements.mfaConfirmCode.value = "";
    submit.disabled = false;
  }
}

function closeKeyDialog() {
  elements.keyPassword.value = "";
  elements.keyMfa.value = "";
  elements.keyOutput.textContent = "";
  elements.keyOutput.hidden = true;
  elements.keyResult.textContent = "";
  if (elements.keyDialog.open) {
    elements.keyDialog.close();
  }
}

async function rotateHumanKey(event) {
  event.preventDefault();
  const submit = elements.keyForm.querySelector("button[type='submit']");
  submit.disabled = true;
  try {
    const rotated = await requestJson("/api/v1/orbit/security/human-keys/rotate", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": state.csrfToken },
      body: JSON.stringify({
        password: elements.keyPassword.value,
        ...mfaProof(elements.keyMfa.value),
        label: elements.keyLabel.value.trim(),
      }),
    });
    elements.keyOutput.hidden = false;
    elements.keyOutput.textContent = rotated.access_key;
    elements.keyResult.textContent = "新 Key 仅显示一次；旧 Human Key 已全部撤销。";
    elements.keyResult.className = "form-status success";
    elements.keyPassword.value = "";
    elements.keyMfa.value = "";
    await loadDashboard();
  } catch (error) {
    elements.keyResult.textContent = error.message;
    elements.keyResult.className = "form-status error";
  } finally {
    elements.keyPassword.value = "";
    elements.keyMfa.value = "";
    submit.disabled = false;
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
  setFormStatus("正在验证身份并建立短期安全会话…");
  try {
    const browserSession = await requestJson("/api/v1/orbit/session", {
      method: "POST",
      headers: { Authorization: `Bearer ${candidate}` },
    });
    state.csrfToken = browserSession.csrf_token;
    elements.accessKey.value = "";
    await loadDashboard();
    setFormStatus("身份验证成功，访问密钥已从页面清除。", "success");
  } catch (error) {
    elements.accessKey.value = "";
    setFormStatus(error.message, "error");
  } finally {
    submit.disabled = false;
  }
}

async function signOut() {
  let revoked = false;
  try {
    await requestJson("/api/v1/orbit/session", {
      method: "DELETE",
      headers: state.csrfToken ? { "X-CSRF-Token": state.csrfToken } : {},
    });
    revoked = true;
  } catch (_error) {
    // Closing the local view does not prove that the server revoked the session.
  } finally {
    closeApprovalDialog();
    closePairingDialog();
    closeRevokeDialog();
    closeMfaDialog();
    closeKeyDialog();
    state.dashboard = null;
    state.csrfToken = "";
    clearSensitiveInputs();
    elements.workspaceView.hidden = true;
    elements.welcomeView.hidden = false;
    if (revoked) {
      setFormStatus("浏览器会话已撤销。", "success");
      setConnection("已退出星轨");
    } else {
      setFormStatus("当前视图已关闭，但服务器会话撤销未确认。恢复网络后请再次退出。", "error");
      setConnection("会话撤销未确认", "error");
    }
    (state.authConfig?.self_service_enabled ? elements.loginEmail : elements.accessKey).focus();
  }
}

async function decideApproval(event) {
  event.preventDefault();
  const approvalId = elements.approvalId.value;
  const decision = elements.approvalDecision.value;
  const candidate = elements.approvalAccessKey.value.trim();
  const mfa = elements.approvalMfa.value.trim();
  if (!state.csrfToken || !approvalId || !["approved", "rejected"].includes(decision)) {
    elements.approvalResult.textContent = "审批上下文已失效，请关闭窗口并刷新星轨。";
    elements.approvalResult.className = "form-status error";
    return;
  }
  if (!validReauthenticationCandidate(candidate)) {
    elements.approvalResult.textContent = "请输入当前密码（或有效的兼容 Human Key）。";
    elements.approvalResult.className = "form-status error";
    return;
  }
  elements.approvalSubmit.disabled = true;
  elements.approvalResult.textContent = "正在重新验证身份并签发一次性确认…";
  elements.approvalResult.className = "form-status";
  try {
    let confirmation;
    try {
      const proof = reauthentication(candidate, mfa, {
        intent: decision === "approved" ? "approve" : "reject",
      });
      confirmation = await requestJson(
        `/api/v1/orbit/approval-requests/${encodeURIComponent(approvalId)}/confirmation`,
        {
          method: "POST",
          headers: proof.headers,
          body: JSON.stringify(proof.payload),
        },
      );
    } finally {
      elements.approvalAccessKey.value = "";
      elements.approvalMfa.value = "";
    }
    elements.approvalResult.textContent = "身份已确认，正在原子写入审批决定…";
    const note = elements.approvalNote.value.trim();
    await requestJson(
      `/api/v1/orbit/approval-requests/${encodeURIComponent(approvalId)}/decision`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": `xinggui-${crypto.randomUUID()}`,
          "X-CSRF-Token": state.csrfToken,
          "X-Human-Confirmation": confirmation.confirmation_token,
        },
        body: JSON.stringify({ decision, note: note || null }),
      },
    );
    closeApprovalDialog();
    await loadDashboard();
    setConnection("审批决定已记录，等待 Agent 轮询", "success");
  } catch (error) {
    elements.approvalAccessKey.value = "";
    elements.approvalMfa.value = "";
    elements.approvalResult.textContent = error.message;
    elements.approvalResult.className = "form-status error";
  } finally {
    elements.approvalSubmit.disabled = false;
  }
}

async function restoreSession() {
  try {
    const browserSession = await requestJson("/api/v1/orbit/session");
    state.csrfToken = browserSession.csrf_token;
    await loadDashboard();
  } catch (error) {
    state.csrfToken = "";
    elements.workspaceView.hidden = true;
    elements.welcomeView.hidden = false;
    if (error.status === 401) {
      setConnection("等待进入星轨");
      return;
    }
    setFormStatus("暂时无法恢复星轨会话，请稍后重试。", "error");
  }
}

elements.accessForm.addEventListener("submit", enterOrbit);
elements.loginForm.addEventListener("submit", loginHuman);
elements.openRegister.addEventListener("click", () => {
  elements.registerResult.textContent = "邮箱验证码有效期有限，请在收到后及时完成注册。";
  elements.registerDialog.showModal();
  elements.registerEmail.focus();
});
elements.registerForm.addEventListener("submit", registerHuman);
elements.registerSendCode.addEventListener("click", () => sendEmailChallenge("register"));
elements.registerClose.addEventListener("click", closeRegisterDialog);
elements.registerCancel.addEventListener("click", closeRegisterDialog);
elements.registerDialog.addEventListener("close", closeRegisterDialog);
elements.openRecovery.addEventListener("click", () => {
  elements.recoveryResult.textContent = "重设密码将撤销旧浏览器会话与所有兼容 Human Key。";
  elements.recoveryDialog.showModal();
  elements.recoveryEmail.focus();
});
elements.recoveryForm.addEventListener("submit", recoverHuman);
elements.recoverySendCode.addEventListener("click", () => sendEmailChallenge("recover"));
elements.recoveryClose.addEventListener("click", closeRecoveryDialog);
elements.recoveryCancel.addEventListener("click", closeRecoveryDialog);
elements.recoveryDialog.addEventListener("close", closeRecoveryDialog);
elements.refresh.addEventListener("click", async () => {
  try {
    await loadDashboard();
  } catch (error) {
    elements.overviewCopy.textContent = error.message;
  }
});
elements.signOut.addEventListener("click", signOut);
elements.approvalForm.addEventListener("submit", decideApproval);
elements.approvalClose.addEventListener("click", closeApprovalDialog);
elements.approvalCancel.addEventListener("click", closeApprovalDialog);
elements.approvalDialog.addEventListener("close", closeApprovalDialog);
elements.openPairing.addEventListener("click", () => openPairingDialog());
elements.pairingForm.addEventListener("submit", decidePairing);
elements.pairingDeny.addEventListener("click", (event) => decidePairing(event, "denied"));
elements.pairingClose.addEventListener("click", () => closePairingDialog());
elements.pairingCancel.addEventListener("click", () => closePairingDialog());
elements.pairingDialog.addEventListener("close", () => closePairingDialog());
elements.pairingId.addEventListener("change", loadPairingPreview);
elements.revokeForm.addEventListener("submit", revokeConnector);
elements.revokeClose.addEventListener("click", closeRevokeDialog);
elements.revokeCancel.addEventListener("click", closeRevokeDialog);
elements.revokeDialog.addEventListener("close", closeRevokeDialog);
elements.openMfa.addEventListener("click", () => {
  elements.mfaResult.textContent = "重新验证后生成只在当前窗口显示的认证器密钥。";
  elements.mfaDialog.showModal();
  elements.mfaPassword.focus();
});
elements.mfaCreate.addEventListener("click", startMfaSetup);
elements.mfaForm.addEventListener("submit", confirmMfaSetup);
elements.mfaClose.addEventListener("click", closeMfaDialog);
elements.mfaCancel.addEventListener("click", closeMfaDialog);
elements.mfaDialog.addEventListener("close", closeMfaDialog);
elements.openKeyRotation.addEventListener("click", () => {
  elements.keyResult.textContent = "轮换后旧 Human Key 将立即失效。";
  elements.keyDialog.showModal();
  elements.keyPassword.focus();
});
elements.keyForm.addEventListener("submit", rotateHumanKey);
elements.keyClose.addEventListener("click", closeKeyDialog);
elements.keyCancel.addEventListener("click", closeKeyDialog);
elements.keyDialog.addEventListener("close", closeKeyDialog);

window.addEventListener("pagehide", () => {
  clearSensitiveInputs();
  state.csrfToken = "";
});

async function initializeOrbit() {
  await loadAuthConfig();
  await restoreSession();
}

initializeOrbit();
