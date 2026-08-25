"use strict";

const FALLBACK_CONNECTOR_RELEASE = Object.freeze({
  version: "0.1.0",
  wheel_url: "https://agentpost.me/downloads/agentpost-0.1.0-py3-none-any.whl",
  wheel_sha256: "1fc3f42e8c1141ce65481778587544fc9bf441438c852c0332594ab24a75fdf7",
});
const LOCAL_AGENT_ID_PATTERN = /^[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?$/;

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
  pendingOrganizationInvitation: "",
  managedOrganization: null,
  organizationDomainProofs: new Map(),
  pairingTargetResolution: "pending",
  pairingCreateNewAutomatically: false,
  selectedPairingHost: "",
  pairingTargetAgent: null,
  pairingNewAgentIntent: "",
  connectors: [],
  threads: [],
  selectedThread: null,
  selectedThreadId: "",
  threadFilter: "all",
  threadQuery: "",
  threadOrganization: "",
  threadSearchTimer: null,
  activeModule: "orbit",
  activeSection: "overview",
  lastSectionByModule: {
    orbit: "overview",
    relay: "agents",
    settings: "profile",
  },
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
  oidcEntry: document.querySelector("#oidc-entry"),
  discoverOidc: document.querySelector("#discover-oidc"),
  oidcOptions: document.querySelector("#oidc-options"),
  openRegister: document.querySelector("#open-register"),
  openRecovery: document.querySelector("#open-recovery"),
  legacyEntry: document.querySelector("#legacy-entry"),
  accessResult: document.querySelector("#access-result"),
  connectionState: document.querySelector("#connection-state"),
  refresh: document.querySelector("#refresh-dashboard"),
  signOut: document.querySelector("#sign-out"),
  profileRefresh: document.querySelector("#profile-refresh"),
  profileSignOut: document.querySelector("#profile-sign-out"),
  humanName: document.querySelector("#human-name"),
  humanEmail: document.querySelector("#human-email"),
  humanAvatar: document.querySelector("#human-avatar"),
  profileName: document.querySelector("#profile-name"),
  profileEmail: document.querySelector("#profile-email"),
  profileTimezone: document.querySelector("#profile-timezone"),
  primaryNavigation: document.querySelector("#primary-navigation"),
  primaryNavigationItems: Array.from(document.querySelectorAll(".primary-nav-item")),
  contextNavigation: document.querySelector("#context-navigation"),
  contextNavigationGroups: Array.from(document.querySelectorAll("[data-context-module]")),
  contextNavigationItems: Array.from(document.querySelectorAll(".context-nav-item")),
  moduleViews: Array.from(document.querySelectorAll(".module-view")),
  contextEyebrow: document.querySelector("#context-eyebrow"),
  contextTitle: document.querySelector("#context-title"),
  contextCopy: document.querySelector("#context-copy"),
  threadBrowser: document.querySelector("#thread-browser"),
  threadCount: document.querySelector("#thread-count"),
  threadSearchInput: document.querySelector("#thread-search-input"),
  threadOrganizationFilter: document.querySelector("#thread-organization-filter"),
  threadFilters: Array.from(document.querySelectorAll("[data-thread-filter]")),
  threadList: document.querySelector("#thread-list"),
  threadMobileBack: document.querySelector("#thread-mobile-back"),
  threadDetailEmpty: document.querySelector("#thread-detail-empty"),
  threadDetail: document.querySelector("#thread-detail"),
  threadDetailTopic: document.querySelector("#thread-detail-topic"),
  threadDetailParticipants: document.querySelector("#thread-detail-participants"),
  threadLatest: document.querySelector("#thread-latest"),
  overviewCopy: document.querySelector("#overview-copy"),
  metricAgents: document.querySelector("#metric-agents"),
  metricUnread: document.querySelector("#metric-unread"),
  metricPending: document.querySelector("#metric-pending"),
  metricOnline: document.querySelector("#metric-online"),
  metricApprovals: document.querySelector("#metric-approvals"),
  organizationCount: document.querySelector("#organization-count"),
  organizationList: document.querySelector("#organization-list"),
  openOrganizationCreate: document.querySelector("#open-organization-create"),
  agentCount: document.querySelector("#agent-count"),
  agentList: document.querySelector("#agent-list"),
  taskList: document.querySelector("#task-list"),
  approvalList: document.querySelector("#approval-list"),
  messageList: document.querySelector("#message-list"),
  connectorList: document.querySelector("#connector-list"),
  securityStatus: document.querySelector("#security-status"),
  openMfa: document.querySelector("#open-mfa"),
  openKeyRotation: document.querySelector("#open-key-rotation"),
  ssoSecurityCard: document.querySelector("#sso-security-card"),
  openSsoLink: document.querySelector("#open-sso-link"),
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
  pairingDialogSummary: document.querySelector("#pairing-dialog-summary"),
  pairingGuide: document.querySelector("#pairing-guide"),
  pairingApproval: document.querySelector("#pairing-approval"),
  pairingHostCards: Array.from(document.querySelectorAll(".pairing-host-card")),
  pairingChatCard: document.querySelector("#pairing-chat-card"),
  pairingHostName: document.querySelector("#pairing-host-name"),
  pairingChatPrompt: document.querySelector("#pairing-chat-prompt"),
  pairingCopyPrompt: document.querySelector("#pairing-copy-prompt"),
  pairingCopyResult: document.querySelector("#pairing-copy-result"),
  pairingGuideBack: document.querySelector("#pairing-guide-back"),
  pairingGuideCancel: document.querySelector("#pairing-guide-cancel"),
  pairingId: document.querySelector("#pairing-id"),
  pairingUserCode: document.querySelector("#pairing-user-code"),
  pairingCodeFields: document.querySelector("#pairing-code-fields"),
  pairingTargetModeField: document.querySelector("#pairing-target-mode-field"),
  pairingTargetMode: document.querySelector("#pairing-target-mode"),
  pairingTargetSummary: document.querySelector("#pairing-target-summary"),
  pairingHandle: document.querySelector("#pairing-handle"),
  pairingExistingAgentField: document.querySelector("#pairing-existing-agent-field"),
  pairingExistingAgent: document.querySelector("#pairing-existing-agent"),
  pairingNewAgentFields: document.querySelector("#pairing-new-agent-fields"),
  pairingLocalId: document.querySelector("#pairing-local-id"),
  pairingAddressDomain: document.querySelector("#pairing-address-domain"),
  pairingDisplayName: document.querySelector("#pairing-display-name"),
  pairingCapabilities: document.querySelector("#pairing-capabilities"),
  pairingAccessKey: document.querySelector("#pairing-access-key"),
  pairingMfa: document.querySelector("#pairing-mfa"),
  pairingPreview: document.querySelector("#pairing-preview"),
  pairingResult: document.querySelector("#pairing-result"),
  handleDialog: document.querySelector("#handle-dialog"),
  handleForm: document.querySelector("#handle-form"),
  handleClose: document.querySelector("#handle-close"),
  handleCancel: document.querySelector("#handle-cancel"),
  handleSubmit: document.querySelector("#handle-submit"),
  handleAgentId: document.querySelector("#handle-agent-id"),
  agentHandle: document.querySelector("#agent-handle"),
  handleSummary: document.querySelector("#handle-summary"),
  handleResult: document.querySelector("#handle-result"),
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
  deleteAgentDialog: document.querySelector("#delete-agent-dialog"),
  deleteAgentForm: document.querySelector("#delete-agent-form"),
  deleteAgentClose: document.querySelector("#delete-agent-close"),
  deleteAgentCancel: document.querySelector("#delete-agent-cancel"),
  deleteAgentSubmit: document.querySelector("#delete-agent-submit"),
  deleteAgentId: document.querySelector("#delete-agent-id"),
  deleteAgentSummary: document.querySelector("#delete-agent-summary"),
  deleteAgentResult: document.querySelector("#delete-agent-result"),
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
  ssoLinkDialog: document.querySelector("#sso-link-dialog"),
  ssoLinkForm: document.querySelector("#sso-link-form"),
  ssoLinkClose: document.querySelector("#sso-link-close"),
  ssoLinkCancel: document.querySelector("#sso-link-cancel"),
  ssoLinkProvider: document.querySelector("#sso-link-provider"),
  ssoLinkPassword: document.querySelector("#sso-link-password"),
  ssoLinkMfa: document.querySelector("#sso-link-mfa"),
  ssoLinkResult: document.querySelector("#sso-link-result"),
  organizationCreateDialog: document.querySelector("#organization-create-dialog"),
  organizationCreateForm: document.querySelector("#organization-create-form"),
  organizationCreateClose: document.querySelector("#organization-create-close"),
  organizationCreateCancel: document.querySelector("#organization-create-cancel"),
  organizationName: document.querySelector("#organization-name"),
  organizationSlug: document.querySelector("#organization-slug"),
  organizationDescription: document.querySelector("#organization-description"),
  organizationCreateResult: document.querySelector("#organization-create-result"),
  organizationManageDialog: document.querySelector("#organization-manage-dialog"),
  organizationManageTitle: document.querySelector("#organization-manage-title"),
  organizationInviteForm: document.querySelector("#organization-invite-form"),
  organizationManageClose: document.querySelector("#organization-manage-close"),
  organizationManageCancel: document.querySelector("#organization-manage-cancel"),
  organizationManageId: document.querySelector("#organization-manage-id"),
  organizationManageSummary: document.querySelector("#organization-manage-summary"),
  organizationInviteEmail: document.querySelector("#organization-invite-email"),
  organizationInviteRole: document.querySelector("#organization-invite-role"),
  organizationManageResult: document.querySelector("#organization-manage-result"),
  organizationMemberList: document.querySelector("#organization-member-list"),
  organizationInvitationList: document.querySelector("#organization-invitation-list"),
  organizationDomainSection: document.querySelector("#organization-domain-section"),
  organizationDomainName: document.querySelector("#organization-domain-name"),
  organizationDomainAdd: document.querySelector("#organization-domain-add"),
  organizationDomainList: document.querySelector("#organization-domain-list"),
  organizationOidcSection: document.querySelector("#organization-oidc-section"),
  organizationOidcName: document.querySelector("#organization-oidc-name"),
  organizationOidcIssuer: document.querySelector("#organization-oidc-issuer"),
  organizationOidcClientId: document.querySelector("#organization-oidc-client-id"),
  organizationOidcClientSecret: document.querySelector("#organization-oidc-client-secret"),
  organizationOidcAdd: document.querySelector("#organization-oidc-add"),
  organizationOidcList: document.querySelector("#organization-oidc-list"),
  organizationLeave: document.querySelector("#organization-leave"),
};

const MODULE_DEFINITIONS = Object.freeze({
  orbit: Object.freeze({
    label: "星轨",
    title: "协作动态",
    description: "查看 Agent 之间的对话、任务和需要你处理的事项。",
    defaultSection: "overview",
    sections: Object.freeze(["overview", "communications", "tasks", "approvals"]),
  }),
  relay: Object.freeze({
    label: "云驿",
    title: "Agent 与连接",
    description: "管理 Agent 身份、真实连接状态和保留的连接历史。",
    defaultSection: "agents",
    sections: Object.freeze(["agents", "connections"]),
  }),
  settings: Object.freeze({
    label: "设置",
    title: "账户与平台",
    description: "管理你的账户安全、组织关系和平台选项。",
    defaultSection: "profile",
    sections: Object.freeze([
      "profile",
      "security",
      "organizations",
      "notifications",
      "privacy",
      "preferences",
      "governance",
    ]),
  }),
});

function normalizedRoute(module, section) {
  const definition = MODULE_DEFINITIONS[module] || MODULE_DEFINITIONS.orbit;
  const normalizedModule = MODULE_DEFINITIONS[module] ? module : "orbit";
  const normalizedSection = definition.sections.includes(section)
    ? section
    : state.lastSectionByModule[normalizedModule] || definition.defaultSection;
  return { module: normalizedModule, section: normalizedSection };
}

function routeUrl(module, section) {
  const url = new URL(window.location.href);
  url.searchParams.set("module", module);
  url.searchParams.set("view", section);
  url.hash = "";
  return `${url.pathname}${url.search}`;
}

function currentRouteUrlWithoutWorkflowParameters() {
  const url = new URL(window.location.href);
  ["pairing", "code"].forEach((name) => url.searchParams.delete(name));
  url.searchParams.set("module", state.activeModule);
  url.searchParams.set("view", state.activeSection);
  url.hash = "";
  return `${url.pathname}${url.search}`;
}

function applyThreadRouteParameters(parameters) {
  state.threadFilter = parameters.get("filter") === "exception" ? "exception" : "all";
  state.threadQuery = parameters.get("q") || "";
  state.threadOrganization = parameters.get("organization") || "";
  state.selectedThreadId = parameters.get("thread") || "";
  elements.threadSearchInput.value = state.threadQuery;
  elements.threadFilters.forEach((button) => {
    const active = button.dataset.threadFilter === state.threadFilter;
    button.classList.toggle("active", active);
    if (button.getAttribute("aria-disabled") !== "true") {
      button.setAttribute("aria-pressed", String(active));
    }
  });
}

function threadRouteUrl() {
  const url = new URL(window.location.href);
  url.searchParams.set("module", "orbit");
  url.searchParams.set("view", "communications");
  const values = {
    filter: state.threadFilter === "all" ? "" : state.threadFilter,
    q: state.threadQuery,
    organization: state.threadOrganization,
    thread: state.selectedThreadId,
  };
  Object.entries(values).forEach(([name, value]) => {
    if (value) {
      url.searchParams.set(name, value);
    } else {
      url.searchParams.delete(name);
    }
  });
  url.hash = "";
  return `${url.pathname}${url.search}`;
}

function updateThreadWorkspaceMode() {
  const active = state.activeModule === "orbit" && state.activeSection === "communications";
  elements.workspaceView.classList.toggle("thread-workspace-mode", active);
  elements.workspaceView.classList.toggle(
    "thread-detail-open",
    active && Boolean(state.selectedThreadId),
  );
  elements.threadBrowser.hidden = !active;
}

function activateRoute(module, section, { updateHistory = true, focusContent = false } = {}) {
  const route = normalizedRoute(module, section);
  const definition = MODULE_DEFINITIONS[route.module];
  const routeChanged = state.activeModule !== route.module || state.activeSection !== route.section;
  state.activeModule = route.module;
  state.activeSection = route.section;
  state.lastSectionByModule[route.module] = route.section;

  elements.primaryNavigationItems.forEach((item) => {
    const active = item.dataset.module === route.module;
    item.classList.toggle("active", active);
    if (active) {
      item.setAttribute("aria-current", "page");
    } else {
      item.removeAttribute("aria-current");
    }
  });
  elements.contextNavigationGroups.forEach((group) => {
    group.hidden = group.dataset.contextModule !== route.module;
  });
  elements.contextNavigationItems.forEach((item) => {
    const active = item.dataset.module === route.module && item.dataset.section === route.section;
    item.classList.toggle("active", active);
    if (active) {
      item.setAttribute("aria-current", "page");
    } else {
      item.removeAttribute("aria-current");
    }
  });
  elements.moduleViews.forEach((view) => {
    view.hidden = !(view.dataset.module === route.module && view.dataset.section === route.section);
  });
  elements.contextEyebrow.textContent = definition.label;
  elements.contextTitle.textContent = definition.title;
  elements.contextCopy.textContent = definition.description;
  document.title = `星云驿 · ${definition.label}`;
  updateThreadWorkspaceMode();
  if (updateHistory && routeChanged) {
    history.pushState({ module: route.module, section: route.section }, "", routeUrl(route.module, route.section));
  }
  if (focusContent && !elements.workspaceView.hidden) {
    elements.workspaceView.querySelector(".workspace-content")?.focus({ preventScroll: true });
  }
}

function initializeWorkspaceNavigation() {
  const parameters = new URLSearchParams(window.location.search);
  applyThreadRouteParameters(parameters);
  const route = normalizedRoute(parameters.get("module") || "orbit", parameters.get("view") || "");
  activateRoute(route.module, route.section, { updateHistory: false });

  elements.primaryNavigationItems.forEach((item) => {
    item.addEventListener("click", () => {
      const module = item.dataset.module;
      activateRoute(module, state.lastSectionByModule[module] || MODULE_DEFINITIONS[module].defaultSection, {
        focusContent: true,
      });
    });
  });
  elements.contextNavigationItems.forEach((item) => {
    item.addEventListener("click", () => activateRoute(item.dataset.module, item.dataset.section, {
      focusContent: true,
    }));
  });
  [elements.primaryNavigation, elements.contextNavigation].forEach((navigation) => {
    navigation.addEventListener("keydown", (event) => {
      if (!["ArrowDown", "ArrowRight", "ArrowUp", "ArrowLeft"].includes(event.key)) {
        return;
      }
      const visibleItems = Array.from(navigation.querySelectorAll("button:not([hidden])"))
        .filter((item) => item.offsetParent !== null);
      const currentIndex = visibleItems.indexOf(document.activeElement);
      if (currentIndex < 0 || visibleItems.length < 2) {
        return;
      }
      event.preventDefault();
      const direction = ["ArrowDown", "ArrowRight"].includes(event.key) ? 1 : -1;
      visibleItems[(currentIndex + direction + visibleItems.length) % visibleItems.length].focus();
    });
  });
}

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
  if (status === 422 && Array.isArray(error?.details)) {
    const fields = new Set(
      error.details
        .map((detail) => Array.isArray(detail?.loc) ? detail.loc.at(-1) : null)
        .filter(Boolean),
    );
    if (fields.has("local_agent_id")) {
      return "Agent 地址格式不正确：只填写 @ 前面的部分，并使用小写字母、数字、点、下划线或连字符。";
    }
    if (fields.has("capabilities")) {
      return "能力标签格式不正确：请用逗号分隔，最多 64 项，每项不超过 100 个字符。";
    }
    if (fields.has("display_name")) {
      return "Agent 名称格式不正确：名称不能为空，且不能超过 200 个字符。";
    }
    if (fields.has("handle")) {
      return "短名称格式不正确：请使用 3–32 位字母、数字和单个连字符，并以字母开头。";
    }
    return "提交内容格式不正确。请检查页面中填写的 Agent 地址、名称和能力标签。";
  }
  if (status === 409 && Array.isArray(error?.details?.suggestions)) {
    return `这个短名称已被使用。可以试试：${error.details.suggestions.join("、")}。`;
  }
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
  let payload = null;
  if (contentType.includes("application/json")) {
    const responseBody = await response.text();
    payload = responseBody.trim() ? JSON.parse(responseBody) : null;
  }
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
    elements.organizationOidcClientSecret,
    elements.ssoLinkPassword,
    elements.ssoLinkMfa,
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

function emptyStateWithAction(message, label, action) {
  const empty = document.createElement("div");
  empty.className = "empty-state action-empty-state";
  const copy = document.createElement("p");
  copy.textContent = message;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "quiet-button";
  button.textContent = label;
  button.addEventListener("click", action);
  empty.append(copy, button);
  return empty;
}

function statusLabel(value, type = "status") {
  if (type === "approval" && value === "pending") {
    return "待审批";
  }
  const labels = {
    pending: "待处理",
    approved: "已批准",
    rejected: "已拒绝",
    expired: "已过期",
    completed: "已完成",
    partial: "部分完成",
    failed: "失败",
    cancelled: "已取消",
    accepted: "正在投递",
    delivered: "已送达",
    read: "Agent 已读取",
    acked: "Agent 已确认收到",
    replied: "已回复",
    low: "低",
    normal: "普通",
    high: "高",
    urgent: "紧急",
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
    verified: "已验证",
    unknown: "尚未上报",
    healthy: "健康",
    degraded: "降级",
    error: "故障",
    connected: "已连接",
    disconnected: "未连接",
    awaiting_agent: "等待 Agent 完成本机连接",
  };
  return labels[value] || safeText(value);
}

function chip(value, type = "status") {
  const item = document.createElement("span");
  item.className = `data-chip ${type} ${safeText(value, "unknown")}`;
  item.textContent = statusLabel(value, type);
  return item;
}

function renderMetrics(metrics, agents, organizations) {
  elements.metricAgents.textContent = safeText(metrics.agent_count, "0");
  elements.metricUnread.textContent = safeText(metrics.unread_delivery_count, "0");
  elements.metricPending.textContent = safeText(metrics.pending_task_count, "0");
  elements.metricOnline.textContent = safeText(metrics.connected_agent_count, "0");
  elements.metricApprovals.textContent = safeText(metrics.pending_approval_count, "0");
  const active = agents.filter((agent) => agent.status === "active").length;
  elements.overviewCopy.textContent = `你当前可查看 ${agents.length} 个 Agent，其中 ${active} 个处于可用状态，并加入 ${organizations.length} 个组织范围。通信是否送达、任务是否完成和审批是否通过会分别显示。`;
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
    if (["owner", "admin", "member", "auditor"].includes(organization.membership_role)) {
      const actions = document.createElement("div");
      actions.className = "organization-card-actions";
      const manage = document.createElement("button");
      manage.type = "button";
      manage.className = "quiet-button";
      manage.textContent = ["owner", "admin"].includes(organization.membership_role)
        ? "治理组织"
        : "查看成员";
      manage.addEventListener("click", () => openOrganizationManagement(organization));
      actions.append(manage);
      card.append(actions);
    }
    fragment.append(card);
  });
  elements.organizationList.append(fragment);
}

function closeOrganizationCreateDialog() {
  elements.organizationName.value = "";
  elements.organizationSlug.value = "";
  elements.organizationDescription.value = "";
  elements.organizationCreateResult.textContent = "";
  if (elements.organizationCreateDialog.open) {
    elements.organizationCreateDialog.close();
  }
}

async function createOrganization(event) {
  event.preventDefault();
  const submit = elements.organizationCreateForm.querySelector("button[type='submit']");
  submit.disabled = true;
  try {
    await requestJson("/api/v1/orbit/organizations", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": state.csrfToken },
      body: JSON.stringify({
        slug: elements.organizationSlug.value.trim().toLowerCase(),
        name: elements.organizationName.value.trim(),
        description: elements.organizationDescription.value.trim() || null,
      }),
    });
    closeOrganizationCreateDialog();
    await loadDashboard();
    setConnection("组织已创建，你是首位 Owner", "success");
  } catch (error) {
    elements.organizationCreateResult.textContent = error.message;
    elements.organizationCreateResult.className = "form-status error";
  } finally {
    submit.disabled = false;
  }
}

function closeOrganizationManagement() {
  elements.organizationInviteEmail.value = "";
  elements.organizationDomainName.value = "";
  elements.organizationOidcName.value = "";
  elements.organizationOidcIssuer.value = "";
  elements.organizationOidcClientId.value = "";
  elements.organizationOidcClientSecret.value = "";
  elements.organizationManageResult.textContent = "";
  elements.organizationMemberList.replaceChildren();
  elements.organizationInvitationList.replaceChildren();
  elements.organizationDomainList.replaceChildren();
  elements.organizationOidcList.replaceChildren();
  state.managedOrganization = null;
  state.organizationDomainProofs.clear();
  if (elements.organizationManageDialog.open) {
    elements.organizationManageDialog.close();
  }
}

function governanceRow(primary, secondary) {
  const row = document.createElement("div");
  row.className = "governance-row";
  const identity = document.createElement("div");
  const title = document.createElement("strong");
  title.textContent = primary;
  const detail = document.createElement("span");
  detail.textContent = secondary;
  identity.append(title, detail);
  const actions = document.createElement("div");
  actions.className = "governance-row-actions";
  row.append(identity, actions);
  return { row, actions };
}

async function changeOrganizationRole(memberId, role) {
  const organization = state.managedOrganization;
  if (!organization) {
    return;
  }
  try {
    await requestJson(
      `/api/v1/orbit/organizations/${encodeURIComponent(organization.id)}/members/${encodeURIComponent(memberId)}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": state.csrfToken },
        body: JSON.stringify({ role }),
      },
    );
    await loadOrganizationManagement();
    await loadDashboard();
  } catch (error) {
    elements.organizationManageResult.textContent = error.message;
    elements.organizationManageResult.className = "form-status error";
  }
}

async function removeOrganizationMember(memberId) {
  const organization = state.managedOrganization;
  if (!organization) {
    return;
  }
  try {
    await requestJson(
      `/api/v1/orbit/organizations/${encodeURIComponent(organization.id)}/members/${encodeURIComponent(memberId)}`,
      { method: "DELETE", headers: { "X-CSRF-Token": state.csrfToken } },
    );
    await loadOrganizationManagement();
    await loadDashboard();
  } catch (error) {
    elements.organizationManageResult.textContent = error.message;
    elements.organizationManageResult.className = "form-status error";
  }
}

function renderOrganizationMembers(members) {
  elements.organizationMemberList.replaceChildren();
  const organization = state.managedOrganization;
  const actorRole = organization?.membership_role;
  const currentUserId = String(state.dashboard?.user?.id || "");
  if (!members.length) {
    elements.organizationMemberList.append(emptyState("暂无成员。"));
    return;
  }
  members.forEach((member) => {
    const { row, actions } = governanceRow(member.human_email, statusLabel(member.role));
    const isSelf = String(member.human_user_id) === currentUserId;
    const canManage = actorRole === "owner"
      || (actorRole === "admin" && ["member", "auditor"].includes(member.role));
    if (canManage && !isSelf) {
      const roleSelect = document.createElement("select");
      const allowedRoles = actorRole === "owner"
        ? ["owner", "admin", "member", "auditor"]
        : ["member", "auditor"];
      allowedRoles.forEach((role) => {
        const option = document.createElement("option");
        option.value = role;
        option.textContent = statusLabel(role);
        option.selected = role === member.role;
        roleSelect.append(option);
      });
      roleSelect.setAttribute("aria-label", `${member.human_email} 的角色`);
      const save = document.createElement("button");
      save.type = "button";
      save.className = "quiet-button";
      save.textContent = "保存";
      save.addEventListener("click", () => changeOrganizationRole(member.human_user_id, roleSelect.value));
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "quiet-button danger";
      remove.textContent = "移除";
      remove.addEventListener("click", () => removeOrganizationMember(member.human_user_id));
      actions.append(roleSelect, save, remove);
    }
    elements.organizationMemberList.append(row);
  });
}

async function revokeOrganizationInvitation(invitationId) {
  const organization = state.managedOrganization;
  if (!organization) {
    return;
  }
  try {
    await requestJson(
      `/api/v1/orbit/organizations/${encodeURIComponent(organization.id)}/invitations/${encodeURIComponent(invitationId)}`,
      { method: "DELETE", headers: { "X-CSRF-Token": state.csrfToken } },
    );
    await loadOrganizationManagement();
  } catch (error) {
    elements.organizationManageResult.textContent = error.message;
    elements.organizationManageResult.className = "form-status error";
  }
}

function renderOrganizationInvitations(invitations) {
  elements.organizationInvitationList.replaceChildren();
  if (!invitations.length) {
    elements.organizationInvitationList.append(emptyState("暂无邀请记录。"));
    return;
  }
  invitations.forEach((invitation) => {
    const { row, actions } = governanceRow(
      invitation.email,
      `${statusLabel(invitation.role)} · ${statusLabel(invitation.status)} · ${dateText(invitation.expires_at)}`,
    );
    if (invitation.status === "pending") {
      const revoke = document.createElement("button");
      revoke.type = "button";
      revoke.className = "quiet-button danger";
      revoke.textContent = "撤销";
      revoke.addEventListener("click", () => revokeOrganizationInvitation(invitation.invitation_id));
      actions.append(revoke);
    }
    elements.organizationInvitationList.append(row);
  });
}

async function verifyOrganizationDomain(domainId) {
  const organization = state.managedOrganization;
  if (!organization) {
    return;
  }
  try {
    await requestJson(
      `/api/v1/orbit/organizations/${encodeURIComponent(organization.id)}/domains/${encodeURIComponent(domainId)}/verify`,
      { method: "POST", headers: { "X-CSRF-Token": state.csrfToken } },
    );
    state.organizationDomainProofs.delete(String(domainId));
    elements.organizationManageResult.textContent = "域名 DNS 所有权已验证。";
    elements.organizationManageResult.className = "form-status success";
    await loadOrganizationManagement();
  } catch (error) {
    elements.organizationManageResult.textContent = `${error.message} 请确认 TXT 记录已生效。`;
    elements.organizationManageResult.className = "form-status error";
  }
}

async function revokeOrganizationDomain(domainId) {
  const organization = state.managedOrganization;
  if (!organization) {
    return;
  }
  try {
    await requestJson(
      `/api/v1/orbit/organizations/${encodeURIComponent(organization.id)}/domains/${encodeURIComponent(domainId)}`,
      { method: "DELETE", headers: { "X-CSRF-Token": state.csrfToken } },
    );
    state.organizationDomainProofs.delete(String(domainId));
    elements.organizationManageResult.textContent = "域名认领已撤销。";
    elements.organizationManageResult.className = "form-status success";
    await loadOrganizationManagement();
  } catch (error) {
    elements.organizationManageResult.textContent = error.message;
    elements.organizationManageResult.className = "form-status error";
  }
}

function renderOrganizationDomains(domains) {
  elements.organizationDomainList.replaceChildren();
  const isOwner = state.managedOrganization?.membership_role === "owner";
  if (!domains.length) {
    elements.organizationDomainList.append(emptyState("尚未认领企业域名。"));
    return;
  }
  domains.forEach((domain) => {
    const detail = `${statusLabel(domain.status)} · TXT ${domain.verification_record_name}`;
    const { row, actions } = governanceRow(domain.domain, detail);
    const proof = state.organizationDomainProofs.get(String(domain.domain_id));
    if (proof) {
      const proofOutput = document.createElement("code");
      proofOutput.className = "domain-proof";
      proofOutput.textContent = `${domain.verification_record_name}\n${proof}`;
      row.firstElementChild.append(proofOutput);
    }
    if (isOwner) {
      if (domain.status === "pending") {
        const verify = document.createElement("button");
        verify.type = "button";
        verify.className = "quiet-button";
        verify.textContent = "验证 DNS";
        verify.addEventListener("click", () => verifyOrganizationDomain(domain.domain_id));
        actions.append(verify);
      }
      const revoke = document.createElement("button");
      revoke.type = "button";
      revoke.className = "quiet-button danger";
      revoke.textContent = "撤销";
      revoke.addEventListener("click", () => revokeOrganizationDomain(domain.domain_id));
      actions.append(revoke);
    }
    elements.organizationDomainList.append(row);
  });
}

async function addOrganizationDomain() {
  const organization = state.managedOrganization;
  const domain = elements.organizationDomainName.value.trim();
  if (!organization || organization.membership_role !== "owner" || !domain) {
    elements.organizationManageResult.textContent = "请输入要认领的企业域名。";
    elements.organizationManageResult.className = "form-status error";
    return;
  }
  elements.organizationDomainAdd.disabled = true;
  try {
    const created = await requestJson(
      `/api/v1/orbit/organizations/${encodeURIComponent(organization.id)}/domains`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": state.csrfToken },
        body: JSON.stringify({ domain }),
      },
    );
    state.organizationDomainProofs.set(
      String(created.domain.domain_id),
      created.verification_value,
    );
    elements.organizationDomainName.value = "";
    elements.organizationManageResult.textContent = "请立即复制下方 TXT 记录；验证值关闭窗口后不再显示。";
    elements.organizationManageResult.className = "form-status success";
    await loadOrganizationManagement();
  } catch (error) {
    elements.organizationManageResult.textContent = error.message;
    elements.organizationManageResult.className = "form-status error";
  } finally {
    elements.organizationDomainAdd.disabled = false;
  }
}

async function disableOrganizationOidc(providerId) {
  const organization = state.managedOrganization;
  if (!organization || organization.membership_role !== "owner") {
    return;
  }
  try {
    await requestJson(
      `/api/v1/orbit/organizations/${encodeURIComponent(organization.id)}/oidc-providers/${encodeURIComponent(providerId)}`,
      { method: "DELETE", headers: { "X-CSRF-Token": state.csrfToken } },
    );
    elements.organizationManageResult.textContent = "企业 SSO 已停用；既有 Human 与审计记录保留。";
    elements.organizationManageResult.className = "form-status success";
    await loadOrganizationManagement();
  } catch (error) {
    elements.organizationManageResult.textContent = error.message;
    elements.organizationManageResult.className = "form-status error";
  }
}

function renderOrganizationOidcProviders(providers) {
  elements.organizationOidcList.replaceChildren();
  if (!providers.length) {
    elements.organizationOidcList.append(emptyState("尚未配置企业 SSO。"));
    return;
  }
  providers.forEach((provider) => {
    const { row, actions } = governanceRow(
      safeText(provider.display_name),
      `${safeText(provider.issuer)} · ${statusLabel(provider.status)}`,
    );
    if (provider.status === "active") {
      const disable = document.createElement("button");
      disable.type = "button";
      disable.className = "quiet-button danger";
      disable.textContent = "停用";
      disable.addEventListener("click", () => disableOrganizationOidc(provider.provider_id));
      actions.append(disable);
    }
    elements.organizationOidcList.append(row);
  });
}

async function addOrganizationOidcProvider() {
  const organization = state.managedOrganization;
  const payload = {
    display_name: elements.organizationOidcName.value.trim(),
    issuer: elements.organizationOidcIssuer.value.trim(),
    client_id: elements.organizationOidcClientId.value.trim(),
    client_secret: elements.organizationOidcClientSecret.value,
  };
  if (
    !organization ||
    organization.membership_role !== "owner" ||
    !payload.display_name ||
    !payload.issuer ||
    !payload.client_id ||
    payload.client_secret.length < 12
  ) {
    elements.organizationManageResult.textContent = "请完整填写企业 SSO 配置；Client Secret 至少 12 个字符。";
    elements.organizationManageResult.className = "form-status error";
    return;
  }
  elements.organizationOidcAdd.disabled = true;
  try {
    await requestJson(
      `/api/v1/orbit/organizations/${encodeURIComponent(organization.id)}/oidc-providers`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": state.csrfToken },
        body: JSON.stringify(payload),
      },
    );
    elements.organizationOidcName.value = "";
    elements.organizationOidcIssuer.value = "";
    elements.organizationOidcClientId.value = "";
    elements.organizationOidcClientSecret.value = "";
    elements.organizationManageResult.textContent = "企业 SSO 已启用；Client Secret 不会再次显示。";
    elements.organizationManageResult.className = "form-status success";
    await loadOrganizationManagement();
  } catch (error) {
    elements.organizationOidcClientSecret.value = "";
    elements.organizationManageResult.textContent = error.message;
    elements.organizationManageResult.className = "form-status error";
  } finally {
    elements.organizationOidcAdd.disabled = false;
  }
}

async function loadOrganizationManagement() {
  const organization = state.managedOrganization;
  if (!organization) {
    return;
  }
  const isManager = ["owner", "admin"].includes(organization.membership_role);
  elements.organizationInviteEmail.disabled = !isManager;
  elements.organizationInviteRole.disabled = !isManager;
  elements.organizationInviteForm.querySelector("button[type='submit']").hidden = !isManager;
  elements.organizationInvitationList.hidden = !isManager;
  const isOwner = organization.membership_role === "owner";
  elements.organizationDomainName.disabled = !isOwner;
  elements.organizationDomainAdd.hidden = !isOwner;
  elements.organizationOidcSection.hidden = !(
    isOwner && Boolean(state.authConfig?.enterprise_oidc_enabled)
  );
  const members = await requestJson(
    `/api/v1/orbit/organizations/${encodeURIComponent(organization.id)}/members`,
  );
  renderOrganizationMembers(Array.isArray(members.items) ? members.items : []);
  if (isManager) {
    const invitations = await requestJson(
      `/api/v1/orbit/organizations/${encodeURIComponent(organization.id)}/invitations`,
    );
    renderOrganizationInvitations(Array.isArray(invitations.items) ? invitations.items : []);
  } else {
    elements.organizationInvitationList.replaceChildren();
  }
  const domains = await requestJson(
    `/api/v1/orbit/organizations/${encodeURIComponent(organization.id)}/domains`,
  );
  renderOrganizationDomains(Array.isArray(domains.items) ? domains.items : []);
  if (isOwner && state.authConfig?.enterprise_oidc_enabled) {
    const providers = await requestJson(
      `/api/v1/orbit/organizations/${encodeURIComponent(organization.id)}/oidc-providers`,
    );
    renderOrganizationOidcProviders(Array.isArray(providers.items) ? providers.items : []);
  } else {
    elements.organizationOidcList.replaceChildren();
  }
}

async function openOrganizationManagement(organization) {
  state.managedOrganization = organization;
  elements.organizationManageId.value = organization.id;
  elements.organizationManageTitle.textContent = `${organization.name} · 组织治理`;
  elements.organizationManageSummary.textContent = `${organization.slug} · 你的角色：${statusLabel(organization.membership_role)}`;
  elements.organizationManageResult.textContent = "组织角色决定治理权限；最后一位 Owner 不能退出或降级。";
  elements.organizationManageDialog.showModal();
  try {
    await loadOrganizationManagement();
  } catch (error) {
    elements.organizationManageResult.textContent = error.message;
    elements.organizationManageResult.className = "form-status error";
  }
}

async function inviteOrganizationMember(event) {
  event.preventDefault();
  const organization = state.managedOrganization;
  if (!organization) {
    return;
  }
  const submit = elements.organizationInviteForm.querySelector("button[type='submit']");
  submit.disabled = true;
  try {
    await requestJson(
      `/api/v1/orbit/organizations/${encodeURIComponent(organization.id)}/invitations`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": state.csrfToken },
        body: JSON.stringify({
          email: elements.organizationInviteEmail.value.trim(),
          role: elements.organizationInviteRole.value,
        }),
      },
    );
    elements.organizationInviteEmail.value = "";
    elements.organizationManageResult.textContent = "邀请已发送；令牌只通过目标邮箱交付。";
    elements.organizationManageResult.className = "form-status success";
    await loadOrganizationManagement();
  } catch (error) {
    elements.organizationManageResult.textContent = error.message;
    elements.organizationManageResult.className = "form-status error";
  } finally {
    submit.disabled = false;
  }
}

async function leaveOrganization() {
  const organization = state.managedOrganization;
  if (!organization) {
    return;
  }
  elements.organizationLeave.disabled = true;
  try {
    await requestJson(
      `/api/v1/orbit/organizations/${encodeURIComponent(organization.id)}/membership`,
      { method: "DELETE", headers: { "X-CSRF-Token": state.csrfToken } },
    );
    closeOrganizationManagement();
    await loadDashboard();
    setConnection("已退出组织", "success");
  } catch (error) {
    elements.organizationManageResult.textContent = error.message;
    elements.organizationManageResult.className = "form-status error";
  } finally {
    elements.organizationLeave.disabled = false;
  }
}

async function maybeAcceptOrganizationInvitation() {
  const token = state.pendingOrganizationInvitation;
  if (!token || !state.csrfToken) {
    return;
  }
  state.pendingOrganizationInvitation = "";
  try {
    await requestJson("/api/v1/orbit/organization-invitations/accept", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": state.csrfToken },
      body: JSON.stringify({ token }),
    });
    await loadDashboard();
    setConnection("组织邀请已接受", "success");
  } catch (error) {
    setConnection("组织邀请无法接受", "error");
    setFormStatus(error.message, "error");
  }
}

function renderAgents(agents) {
  elements.agentList.replaceChildren();
  elements.agentCount.textContent = `${agents.length} 个`;
  if (agents.length === 0) {
    elements.agentList.append(emptyStateWithAction(
      "你还没有连接 Agent。先到连接管理选择 Codex、WorkBuddy 或 OpenClaw，按页面提示完成授权。",
      "前往连接管理",
      () => activateRoute("relay", "connections", { focusContent: true }),
    ));
    return;
  }
  const fragment = document.createDocumentFragment();
  agents.forEach((agent) => {
    const agentConnectors = state.connectors.filter(
      (connector) => String(connector.agent?.id) === String(agent.id),
    );
    const currentConnector = agentConnectors.find(
      (connector) => connector.is_current && connector.status === "active",
    ) || null;
    const connectedConnector = currentConnector?.connection_state === "connected"
      ? currentConnector
      : null;
    const preferredConnector = currentConnector || agentConnectors[0] || null;
    const card = document.createElement("article");
    card.className = "agent-card";
    card.dataset.agentId = String(agent.id);
    card.tabIndex = -1;

    const top = document.createElement("div");
    top.className = "agent-card-top";
    const identity = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = safeText(agent.handle, agent.display_name);
    const displayName = document.createElement("span");
    displayName.textContent = agent.handle
      ? safeText(agent.display_name)
      : "尚未设置短名称";
    identity.append(title, displayName);
    const badges = document.createElement("div");
    badges.className = "agent-status-badges";
    badges.append(chip(
      connectedConnector ? "connected" : currentConnector ? "awaiting_agent" : "disconnected",
    ));
    badges.append(chip(agent.role, "role"));
    top.append(identity, badges);

    const connection = document.createElement("div");
    connection.className = `agent-connection-state ${connectedConnector ? "connected" : currentConnector ? "awaiting" : "disconnected"}`;
    connection.textContent = connectedConnector
      ? `${safeText(connectedConnector.display_name, connectedConnector.connector_type)} 已连接 · ${statusLabel(connectedConnector.health_status)}`
      : currentConnector
      ? `${safeText(currentConnector.display_name, currentConnector.connector_type)} 已获授权，等待 Agent 在本机完成安全设置并首次报到`
      : "当前未连接；Agent 身份和历史仍保留";

    const identityDetails = document.createElement("details");
    identityDetails.className = "agent-identity-details";
    const identitySummary = document.createElement("summary");
    identitySummary.textContent = "查看底层身份";
    const technicalAddress = document.createElement("span");
    technicalAddress.textContent = safeText(agent.address);
    identityDetails.append(identitySummary, technicalAddress);

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
    card.append(top, connection, identityDetails);
    if (agent.organization) {
      const organization = document.createElement("div");
      organization.className = "agent-organization";
      organization.textContent = `${safeText(agent.organization.name)} · ${agent.access_source === "organization" ? "组织授权" : "直接授权"}`;
      card.append(organization);
    }
    card.append(capabilities, stats);
    if (agent.role === "owner") {
      const actions = document.createElement("div");
      actions.className = "agent-card-actions";
      const connect = document.createElement("button");
      connect.type = "button";
      connect.className = "quiet-button";
      connect.textContent = connectedConnector ? "重新连接" : currentConnector ? "继续连接" : "连接";
      connect.addEventListener("click", () => openPairingDialog(
        "",
        "",
        agent,
        safeText(preferredConnector?.connector_type, ""),
      ));
      const editHandle = document.createElement("button");
      editHandle.type = "button";
      editHandle.className = "quiet-button";
      editHandle.textContent = agent.handle ? "修改短名称" : "设置短名称";
      editHandle.addEventListener("click", () => openHandleDialog(agent));
      actions.append(connect);
      if (currentConnector) {
        const disconnect = document.createElement("button");
        disconnect.type = "button";
        disconnect.className = "quiet-button";
        disconnect.textContent = connectedConnector ? "断开" : "取消未完成连接";
        disconnect.addEventListener("click", () => openRevokeDialog(currentConnector));
        actions.append(disconnect);
      }
      actions.append(editHandle);
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "quiet-button danger";
      remove.textContent = "删除 Agent";
      remove.addEventListener("click", () => openDeleteAgentDialog(agent));
      actions.append(remove);
      card.append(actions);
    }
    fragment.append(card);
  });
  elements.agentList.append(fragment);
}

function openHandleDialog(agent) {
  elements.handleAgentId.value = safeText(agent.id, "");
  elements.agentHandle.value = safeText(agent.handle, "");
  elements.handleSummary.textContent = `为 ${safeText(agent.display_name, "这个 Agent")} 设置容易记住的称呼。`;
  elements.handleResult.textContent = agent.handle
    ? "修改后，底层身份、权限、连接和历史消息都保持不变。"
    : "设置后，你可以在收件人、任务和 Agent 列表中使用这个短名称。";
  elements.handleResult.className = "form-status";
  elements.handleDialog.showModal();
  elements.agentHandle.focus();
}

function closeHandleDialog() {
  elements.handleAgentId.value = "";
  elements.agentHandle.value = "";
  elements.handleResult.textContent = "";
  if (elements.handleDialog.open) {
    elements.handleDialog.close();
  }
}

async function saveAgentHandle(event) {
  event.preventDefault();
  const agentId = elements.handleAgentId.value.trim();
  const handle = elements.agentHandle.value.trim().toLowerCase();
  elements.agentHandle.value = handle;
  if (
    !agentId
    || (handle && (
      handle.length < 3
      || handle.length > 32
      || !/^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/.test(handle)
    ))
  ) {
    elements.handleResult.textContent = "请使用 3–32 位字母、数字和单个连字符，并以字母开头。";
    elements.handleResult.className = "form-status error";
    return;
  }
  elements.handleSubmit.disabled = true;
  elements.handleResult.textContent = "正在保存短名称…";
  elements.handleResult.className = "form-status";
  try {
    await requestJson(`/api/v1/orbit/agents/${encodeURIComponent(agentId)}/handle`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": state.csrfToken },
      body: JSON.stringify({ handle: handle || null }),
    });
    closeHandleDialog();
    await loadDashboard();
    setConnection(handle ? `短名称 ${handle} 已保存` : "Agent 短名称已移除", "success");
  } catch (error) {
    elements.handleResult.textContent = error.message;
    elements.handleResult.className = "form-status error";
  } finally {
    elements.handleSubmit.disabled = false;
  }
}

function openRevokeDialog(connector) {
  elements.revokeConnectorId.value = safeText(connector.connector_id, "");
  const agentLabel = connector.agent?.handle || connector.agent?.display_name || connector.agent?.address;
  elements.revokeSummary.textContent = `将断开 ${safeText(agentLabel, "这个 Agent")} 当前使用的 ${safeText(connector.display_name)} 连接。`;
  elements.revokeResult.textContent = "请重新输入当前密码（或兼容 Human Key）；凭证验证后立即清除。";
  elements.revokeResult.className = "form-status";
  elements.revokeDialog.showModal();
  elements.revokeAccessKey.focus();
}

function connectorCard(connector, historical = false) {
  const card = document.createElement("article");
  card.className = historical ? "connector-card historical" : "connector-card";
  const heading = document.createElement("div");
  heading.className = "connector-heading";
  const identity = document.createElement("div");
  const name = document.createElement("strong");
  const agentLabel = connector.agent?.handle || connector.agent?.display_name || "这个 Agent";
  name.textContent = safeText(agentLabel, "这个 Agent");
  const connectionName = document.createElement("span");
  connectionName.textContent = safeText(connector.display_name, "本机连接");
  identity.append(name, connectionName);
  heading.append(identity, chip(historical ? connector.status : connector.connection_state));

  const facts = document.createElement("dl");
  [
    ["Agent 类型", connector.connector_type],
    ["设备", connector.device_name],
    ["最近连接", dateText(connector.last_seen_at)],
    ["最近报到", dateText(connector.last_heartbeat_at)],
    ["连接状态", statusLabel(connector.health_status)],
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

  const technicalDetails = document.createElement("details");
  technicalDetails.className = "connector-technical-details";
  const technicalSummary = document.createElement("summary");
  technicalSummary.textContent = "查看连接技术信息";
  const technicalFacts = document.createElement("dl");
  [
    ["规范地址", connector.agent?.address],
    ["连接版本", connector.client_version],
  ].forEach(([label, value]) => {
    const cell = document.createElement("div");
    const term = document.createElement("dt");
    term.textContent = label;
    const detail = document.createElement("dd");
    detail.textContent = safeText(value);
    cell.append(term, detail);
    technicalFacts.append(cell);
  });
  technicalDetails.append(technicalSummary, technicalFacts);
  card.append(technicalDetails);

  if (connector.is_current && connector.status === "active") {
    const actions = document.createElement("div");
    actions.className = "connector-actions";
    const current = document.createElement("span");
    const connected = connector.connection_state === "connected";
    current.textContent = connected
      ? "当前连接 · Agent 身份和历史记录会独立保留"
      : "授权已完成，但本机配置和首次报到尚未完成；现在不能收发消息";
    const revoke = document.createElement("button");
    revoke.type = "button";
    revoke.className = "quiet-button danger";
    revoke.textContent = connected ? "撤销连接" : "取消未完成连接";
    revoke.addEventListener("click", () => openRevokeDialog(connector));
    actions.append(current, revoke);
    card.append(actions);
  }
  return card;
}

function renderConnectors(connectors) {
  elements.connectorList.replaceChildren();
  if (!connectors.length) {
    elements.connectorList.append(emptyStateWithAction(
      "还没有连接 Agent。选择你常用的 Agent 类型，然后复制一句话发给它即可。",
      "连接新的 Agent",
      () => openPairingDialog(),
    ));
    return;
  }
  const currentConnectors = connectors.filter(
    (connector) => connector.is_current && connector.status === "active",
  );
  const historicalConnectors = connectors.filter(
    (connector) => !(connector.is_current && connector.status === "active"),
  );
  const fragment = document.createDocumentFragment();
  if (currentConnectors.length === 0) {
    fragment.append(emptyState("当前没有已连接的 Agent；已有身份和历史仍保留。"));
  } else {
    currentConnectors.forEach((connector) => fragment.append(connectorCard(connector)));
  }
  if (historicalConnectors.length > 0) {
    const history = document.createElement("details");
    history.className = "connector-history";
    const summary = document.createElement("summary");
    summary.textContent = `查看 ${historicalConnectors.length} 条历史连接记录`;
    const explanation = document.createElement("p");
    explanation.textContent = "这些是同一 Agent 过去使用过的连接，仅为审计保留，不是多个可删除的 Agent。";
    const historyGrid = document.createElement("div");
    historyGrid.className = "connector-history-grid";
    historicalConnectors.forEach((connector) => {
      historyGrid.append(connectorCard(connector, true));
    });
    history.append(summary, explanation, historyGrid);
    fragment.append(history);
  }
  elements.connectorList.append(fragment);
}

function showPairingGuide(targetAgent = state.pairingTargetAgent, preferredHost = "") {
  state.pairingTargetAgent = targetAgent || null;
  state.pairingNewAgentIntent = targetAgent
    ? ""
    : state.pairingNewAgentIntent || crypto.randomUUID();
  elements.pairingGuide.hidden = false;
  elements.pairingApproval.hidden = true;
  elements.pairingDialogSummary.textContent = targetAgent
    ? `重新连接 ${safeText(targetAgent.handle, targetAgent.display_name)}。复制接入码到它的普通对话框，原身份和历史保持不变。`
    : "先选择你正在使用的 Agent。星轨会生成一段接入码，复制到它的普通对话框即可。";
  state.selectedPairingHost = "";
  elements.pairingHostCards.forEach((button) => {
    button.classList.remove("selected");
    button.setAttribute("aria-pressed", "false");
  });
  elements.pairingChatCard.hidden = true;
  elements.pairingChatPrompt.textContent = "";
  elements.pairingCopyResult.textContent = "";
  elements.pairingCopyResult.className = "form-status";
  if (PAIRING_HOSTS[preferredHost]) {
    selectPairingHost(preferredHost);
  }
  elements.pairingHostCards[0]?.focus();
}

const PAIRING_HOSTS = Object.freeze({
  codex: { name: "Codex", code: "AP-CODEX-V1" },
  workbuddy: { name: "WorkBuddy", code: "AP-WORKBUDDY-V1" },
  openclaw: { name: "OpenClaw", code: "AP-OPENCLAW-V1" },
});

function pairingPrompt(host) {
  const selected = PAIRING_HOSTS[host];
  if (!selected) {
    return "";
  }
  const target = state.pairingTargetAgent;
  const targetLabel = target ? safeText(target.handle, target.display_name) : "";
  const targetQuery = target?.id
    ? `?agent=${encodeURIComponent(target.id)}`
    : `?new=${encodeURIComponent(state.pairingNewAgentIntent)}`;
  return [
    target
      ? `请把当前 ${selected.name} 重新连接到我已有的 Agent“${targetLabel}”，保留原身份和历史。`
      : `请把当前 ${selected.name} 作为新的独立 Agent 连接到我的星云驿。`,
    `接入码：${selected.code} https://agentpost.me/connect/${host}${targetQuery}`,
    "请读取这个官方接入页并直接完成安装和授权。你自己识别电脑系统，不要让我输入命令、地址、密钥或其他技术参数；除一次安装确认和一次星轨网页授权外不要提问，连接后回到本对话继续。",
  ].join("\n");
}

function selectPairingHost(host) {
  const selected = PAIRING_HOSTS[host];
  if (!selected) {
    return;
  }
  state.selectedPairingHost = host;
  elements.pairingHostCards.forEach((button) => {
    const isSelected = button.dataset.connectorType === host;
    button.classList.toggle("selected", isSelected);
    button.setAttribute("aria-pressed", String(isSelected));
  });
  elements.pairingHostName.textContent = selected.name;
  elements.pairingChatPrompt.textContent = pairingPrompt(host);
  elements.pairingChatCard.hidden = false;
  elements.pairingCopyResult.textContent = "";
  elements.pairingCopyPrompt.focus();
}

function showPairingApproval({ allowBack = true } = {}) {
  elements.pairingGuide.hidden = true;
  elements.pairingApproval.hidden = false;
  elements.pairingGuideBack.hidden = !allowBack;
  elements.pairingDialogSummary.textContent = "最后一步只确认这次连接。Agent 身份会自动匹配，长期凭证由本地连接器自动领取，不会显示在星轨中。";
  (elements.pairingId.value ? elements.pairingAccessKey : elements.pairingId).focus();
}

async function copyPairingPrompt() {
  const prompt = elements.pairingChatPrompt.textContent.trim();
  if (!prompt || !state.selectedPairingHost) {
    elements.pairingCopyResult.textContent = "请先选择要连接的 Agent。";
    elements.pairingCopyResult.className = "form-status error";
    return;
  }
  const button = elements.pairingCopyPrompt;
  const originalLabel = button.textContent;
  try {
    await navigator.clipboard.writeText(prompt);
    button.textContent = "已复制";
    elements.pairingCopyResult.textContent = `已复制。现在粘贴到 ${PAIRING_HOSTS[state.selectedPairingHost].name} 的对话框并发送。`;
    elements.pairingCopyResult.className = "form-status success";
    setTimeout(() => {
      button.textContent = originalLabel;
    }, 1800);
  } catch (_error) {
    elements.pairingCopyResult.textContent = "浏览器没有允许自动复制。请选中上面那句话后手动复制。";
    elements.pairingCopyResult.className = "form-status error";
  }
}

function closePairingDialog({ clear = true } = {}) {
  elements.pairingAccessKey.value = "";
  elements.pairingMfa.value = "";
  elements.pairingResult.textContent = "";
  if (clear) {
    elements.pairingId.value = "";
    elements.pairingUserCode.value = "";
    elements.pairingCodeFields.hidden = false;
    elements.pairingTargetMode.value = "new";
    elements.pairingExistingAgent.replaceChildren();
    elements.pairingLocalId.value = "";
    elements.pairingDisplayName.value = "";
    elements.pairingCapabilities.value = "";
    elements.pairingHandle.value = "";
    elements.pairingPreview.replaceChildren();
    elements.pairingPreview.hidden = true;
    state.pairingTargetResolution = "pending";
    state.pairingCreateNewAutomatically = false;
    state.pairingRequestSignature = "";
    state.pairingIdempotencyKey = "";
    state.pairingTargetAgent = null;
    state.pairingNewAgentIntent = "";
    updatePairingTargetMode();
  }
  if (elements.pairingDialog.open) {
    elements.pairingDialog.close();
  }
}

function populateExistingAgentOptions() {
  elements.pairingExistingAgent.replaceChildren();
  const agents = Array.isArray(state.dashboard?.agents) ? state.dashboard.agents : [];
  const owned = agents.filter(
    (agent) => agent.access_source === "direct" && agent.role === "owner" && agent.status === "active",
  );
  owned.forEach((agent) => {
    const option = document.createElement("option");
    option.value = agent.id;
    option.textContent = agent.handle
      ? `${safeText(agent.handle)} · ${safeText(agent.display_name)}`
      : safeText(agent.display_name, agent.address);
    elements.pairingExistingAgent.append(option);
  });
  if (!owned.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "没有可迁移的自有 Agent";
    elements.pairingExistingAgent.append(option);
  }
  return owned;
}

function updatePairingTargetMode() {
  if (state.pairingTargetResolution !== "pending") {
    const ambiguous = state.pairingTargetResolution === "ambiguous";
    elements.pairingTargetModeField.hidden = true;
    elements.pairingExistingAgentField.hidden = !ambiguous;
    elements.pairingNewAgentFields.hidden = true;
    elements.pairingLocalId.required = false;
    elements.pairingExistingAgent.required = ambiguous;
    return;
  }
  const existing = elements.pairingTargetMode.value === "existing";
  elements.pairingTargetModeField.hidden = false;
  elements.pairingExistingAgentField.hidden = !existing;
  elements.pairingNewAgentFields.hidden = existing;
  elements.pairingLocalId.required = !existing;
  elements.pairingExistingAgent.required = existing;
}

function configurePairingTarget(pairing) {
  const owned = populateExistingAgentOptions();
  state.pairingCreateNewAutomatically = false;
  elements.pairingTargetSummary.hidden = false;
  const requestedAgentId = safeText(pairing.requested_existing_agent_id, "");
  const requestedAgent = requestedAgentId
    ? owned.find((agent) => String(agent.id) === requestedAgentId)
    : null;
  if (requestedAgent) {
    state.pairingTargetResolution = "automatic-existing";
    elements.pairingTargetMode.value = "existing";
    elements.pairingExistingAgent.value = requestedAgent.id;
    elements.pairingTargetSummary.textContent = `将重新连接 ${safeText(requestedAgent.handle, requestedAgent.display_name)}；原身份、权限、任务和历史保持不变。`;
    elements.pairingSubmit.disabled = false;
  } else if (requestedAgentId) {
    state.pairingTargetResolution = "invalid-target";
    elements.pairingTargetMode.value = "existing";
    elements.pairingTargetSummary.textContent = "这段接入码指定的 Agent 不属于当前账号。请关闭后，从目标 Agent 卡片重新点击“连接”。";
    elements.pairingSubmit.disabled = true;
  } else {
    state.pairingTargetResolution = "automatic-new";
    state.pairingCreateNewAutomatically = true;
    elements.pairingTargetMode.value = "new";
    elements.pairingTargetSummary.textContent = `将为 ${safeText(pairing.connector_display_name, "当前 Agent")} 创建新的独立身份和可读地址，不会替换你已有的任何 Agent。`;
    elements.pairingSubmit.disabled = false;
  }
  updatePairingTargetMode();
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
    configurePairingTarget(pairing);
    elements.pairingResult.textContent = "请核对 Agent 上显示的完整配对码和以上设备信息。";
    elements.pairingResult.className = "form-status";
  } catch (error) {
    elements.pairingPreview.hidden = true;
    elements.pairingResult.textContent = error.message;
    elements.pairingResult.className = "form-status error";
  }
}

async function openPairingDialog(pairingId = "", userCode = "", targetAgent = null, preferredHost = "") {
  state.pairingTargetAgent = targetAgent;
  elements.pairingId.value = pairingId;
  elements.pairingUserCode.value = userCode;
  elements.pairingCodeFields.hidden = Boolean(pairingId && userCode);
  elements.pairingResult.textContent = "请核对工具和设备，确认后连接器会自动恢复原任务。";
  elements.pairingResult.className = "form-status";
  populateExistingAgentOptions();
  updatePairingTargetMode();
  elements.pairingDialog.showModal();
  if (pairingId) {
    showPairingApproval({ allowBack: false });
    await loadPairingPreview();
    return;
  }
  showPairingGuide(targetAgent, preferredHost);
}

function pairingPayload(decision) {
  if (decision === "denied") {
    return { decision: "denied" };
  }
  const handle = elements.pairingHandle.value.trim().toLowerCase() || null;
  elements.pairingHandle.value = handle || "";
  if (state.pairingCreateNewAutomatically) {
    return { decision: "approved", create_new_agent: true, handle };
  }
  if (elements.pairingTargetMode.value === "existing") {
    return {
      decision: "approved",
      existing_agent_id: elements.pairingExistingAgent.value || null,
      handle,
    };
  }
  const capabilities = [...new Set(
    elements.pairingCapabilities.value
      .split(/[,，]/)
      .map((value) => value.trim().toLowerCase())
      .filter(Boolean),
  )];
  const localAgentId = canonicalPairingLocalId(elements.pairingLocalId.value);
  elements.pairingLocalId.value = localAgentId;
  return {
    decision: "approved",
    handle,
    local_agent_id: localAgentId,
    display_name: elements.pairingDisplayName.value.trim() || null,
    capabilities: capabilities.length ? capabilities : null,
  };
}

function managedAgentDomain() {
  return state.authConfig?.managed_agent_domain || "agents.local";
}

function canonicalPairingLocalId(value) {
  const candidate = value.trim().toLowerCase();
  const separator = candidate.lastIndexOf("@");
  if (separator > 0 && candidate.slice(separator + 1) === managedAgentDomain()) {
    return candidate.slice(0, separator);
  }
  return candidate;
}

function pairingPayloadProblem(decision, payload) {
  if (decision !== "approved") {
    return "";
  }
  if (
    payload.handle
    && (
      payload.handle.length < 3
      || payload.handle.length > 32
      || !/^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/.test(payload.handle)
    )
  ) {
    return "短名称请使用 3–32 位字母、数字和单个连字符，并以字母开头。";
  }
  if (payload.create_new_agent || payload.existing_agent_id) {
    return "";
  }
  if (!payload.local_agent_id) {
    return "请为 Agent 设置一个地址。只填写 @ 前面的部分，例如 mars-codex。";
  }
  if (!LOCAL_AGENT_ID_PATTERN.test(payload.local_agent_id)) {
    return `Agent 地址只填写 @${managedAgentDomain()} 前面的部分，并使用小写字母、数字、点、下划线或连字符。`;
  }
  if ((payload.capabilities || []).length > 64 || (payload.capabilities || []).some((value) => value.length > 100)) {
    return "能力标签请用逗号分隔，最多填写 64 项，每项不超过 100 个字符。";
  }
  return "";
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
  const payloadProblem = pairingPayloadProblem(decision, payload);
  if (!state.csrfToken || !pairingId.startsWith("pair_") || !userCode || !validReauthenticationCandidate(humanKey)) {
    elements.pairingResult.textContent = "请填写有效的配对 ID、一次性配对码和当前密码（或兼容 Human Key）。";
    elements.pairingResult.className = "form-status error";
    return;
  }
  if (
    decision === "approved"
    && !payload.create_new_agent
    && !payload.local_agent_id
    && !payload.existing_agent_id
  ) {
    elements.pairingResult.textContent = "请选择这次连接属于哪个 Agent。";
    elements.pairingResult.className = "form-status error";
    return;
  }
  if (payloadProblem) {
    elements.pairingResult.textContent = payloadProblem;
    elements.pairingResult.className = "form-status error";
    elements.pairingLocalId.focus();
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
      ? (payload.create_new_agent
        ? "身份已确认，正在创建 Agent 并完成安全连接…"
        : payload.existing_agent_id
        ? "身份已确认，正在替换当前连接并撤销旧凭证…"
        : "身份已确认，正在创建 Agent 并完成安全连接…")
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
    history.replaceState(
      { module: state.activeModule, section: state.activeSection },
      "",
      currentRouteUrlWithoutWorkflowParameters(),
    );
    await loadDashboard();
    setConnection(
      decision === "approved" ? "Agent 已加入云驿，等待它完成本机安全连接" : "配对已拒绝",
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
    setConnection("连接已断开；Agent 身份和历史记录已保留", "success");
  } catch (error) {
    elements.revokeResult.textContent = error.message;
    elements.revokeResult.className = "form-status error";
  } finally {
    elements.revokeSubmit.disabled = false;
  }
}

function openDeleteAgentDialog(agent) {
  elements.deleteAgentId.value = safeText(agent.id, "");
  elements.deleteAgentSummary.textContent = `确定删除 ${safeText(agent.handle, agent.display_name)} 吗？这个操作只影响该 Agent，不会让其他 Agent 下线。`;
  elements.deleteAgentResult.textContent = "删除后，该 Agent 的当前连接会立即失效，历史记录仍会保留。";
  elements.deleteAgentResult.className = "form-status";
  elements.deleteAgentDialog.showModal();
  elements.deleteAgentCancel.focus();
}

function closeDeleteAgentDialog() {
  elements.deleteAgentId.value = "";
  elements.deleteAgentResult.textContent = "";
  if (elements.deleteAgentDialog.open) {
    elements.deleteAgentDialog.close();
  }
}

async function deleteAgent(event) {
  event.preventDefault();
  const agentId = elements.deleteAgentId.value.trim();
  if (!state.csrfToken || !agentId) {
    elements.deleteAgentResult.textContent = "无法确认要删除的 Agent，请关闭后重试。";
    elements.deleteAgentResult.className = "form-status error";
    return;
  }
  elements.deleteAgentSubmit.disabled = true;
  try {
    await requestJson(`/api/v1/orbit/agents/${encodeURIComponent(agentId)}`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": state.csrfToken },
      body: JSON.stringify({ confirmation: "delete" }),
    });
    closeDeleteAgentDialog();
    await loadDashboard();
    setConnection("Agent 已删除；其他 Agent 的连接未受影响", "success");
  } catch (error) {
    elements.deleteAgentResult.textContent = error.message;
    elements.deleteAgentResult.className = "form-status error";
  } finally {
    elements.deleteAgentSubmit.disabled = false;
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
    heading.append(identity, chip(approval.status, "approval"));

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

function agentDisplayName(agent) {
  return safeText(agent?.handle, agent?.display_name || agent?.address || "Agent");
}

function agentTypeLabel(agent) {
  const labels = { codex: "Codex", workbuddy: "WorkBuddy", openclaw: "OpenClaw" };
  return labels[agent?.agent_type] || (agent?.agent_type ? safeText(agent.agent_type) : "类型未提供");
}

function agentHue(agent) {
  const value = safeText(agent?.id, agent?.address || "agent");
  let hash = 0;
  for (const character of value) {
    hash = ((hash << 5) - hash + character.codePointAt(0)) | 0;
  }
  return Math.abs(hash) % 360;
}

function agentAvatar(agent, className = "agent-mini-avatar") {
  const avatar = document.createElement("span");
  avatar.className = className;
  avatar.style.setProperty("--agent-hue", String(agentHue(agent)));
  avatar.textContent = agentDisplayName(agent).slice(0, 1).toUpperCase();
  avatar.setAttribute("aria-hidden", "true");
  return avatar;
}

function messageTypeLabel(value) {
  const labels = {
    message: "普通消息",
    task: "任务",
    response: "回复",
    request: "请求",
    result: "结果",
    notification: "通知",
    event: "系统事件",
    system: "系统事件",
    error: "异常事件",
  };
  return labels[value] || safeText(value, "消息");
}

function compactThreadContent(value, fallback = "暂无正文摘要") {
  const text = safeText(value, fallback).replace(/\s+/g, " ").trim();
  return text.length > 92 ? `${text.slice(0, 92)}…` : text;
}

function formatFileSize(value) {
  const bytes = Number(value);
  if (!Number.isFinite(bytes) || bytes < 0) {
    return "大小未知";
  }
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function renderThreadOrganizationOptions() {
  const organizations = Array.isArray(state.dashboard?.organizations)
    ? state.dashboard.organizations
    : [];
  elements.threadOrganizationFilter.replaceChildren();
  const all = document.createElement("option");
  all.value = "";
  all.textContent = "全部范围";
  elements.threadOrganizationFilter.append(all);
  organizations.forEach((organization) => {
    const option = document.createElement("option");
    option.value = safeText(organization.id, "");
    option.textContent = safeText(organization.name, organization.slug);
    elements.threadOrganizationFilter.append(option);
  });
  elements.threadOrganizationFilter.value = organizations.some(
    (organization) => String(organization.id) === state.threadOrganization,
  ) ? state.threadOrganization : "";
  if (!elements.threadOrganizationFilter.value) {
    state.threadOrganization = "";
  }
}

function visibleThreadSummaries() {
  return state.threads.filter((thread) => {
    if (state.threadFilter === "exception" && Number(thread.exception_count || 0) === 0) {
      return false;
    }
    if (state.threadOrganization && !(thread.organizations || []).some(
      (organization) => String(organization.id) === state.threadOrganization,
    )) {
      return false;
    }
    return true;
  });
}

function renderThreadList() {
  elements.threadList.replaceChildren();
  const threads = visibleThreadSummaries();
  elements.threadCount.textContent = `${threads.length} 个`;
  if (!threads.length) {
    const hasAgents = Array.isArray(state.dashboard?.agents) && state.dashboard.agents.length > 0;
    if (state.threadQuery) {
      elements.threadList.append(emptyState("没有找到你有权查看且符合搜索条件的对话。"));
    } else if (state.threadFilter === "exception") {
      elements.threadList.append(emptyState("当前授权范围内没有异常对话。"));
    } else if (hasAgents) {
      elements.threadList.append(emptyState("Agent 已连接或已授权，但目前还没有产生协作对话。"));
    } else {
      elements.threadList.append(emptyStateWithAction(
        "连接 Agent 后，它们之间的真实 Thread 会出现在这里。",
        "去云驿连接 Agent",
        () => activateRoute("relay", "connections", { focusContent: true }),
      ));
    }
    return;
  }
  const fragment = document.createDocumentFragment();
  threads.forEach((thread) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "thread-list-item";
    button.classList.toggle("active", String(thread.thread_id) === state.selectedThreadId);
    if (String(thread.thread_id) === state.selectedThreadId) {
      button.setAttribute("aria-current", "true");
    }
    button.setAttribute("aria-label", `打开对话：${safeText(thread.topic, "无主题对话")}`);

    const top = document.createElement("span");
    top.className = "thread-list-top";
    const topic = document.createElement("strong");
    topic.className = "thread-list-topic";
    topic.textContent = safeText(thread.topic, "无主题对话");
    const time = document.createElement("span");
    time.className = "thread-list-time";
    time.textContent = dateText(thread.latest_activity_at);
    top.append(topic, time);

    const participants = document.createElement("span");
    participants.className = "thread-list-participants";
    const avatars = document.createElement("span");
    avatars.className = "thread-avatar-stack";
    (thread.participants || []).slice(0, 3).forEach((agent) => avatars.append(agentAvatar(agent)));
    const names = document.createElement("span");
    names.className = "thread-participant-names";
    names.textContent = (thread.participants || []).map(agentDisplayName).join("、") || "参与 Agent 待确认";
    participants.append(avatars, names);

    const preview = document.createElement("span");
    preview.className = "thread-list-preview";
    preview.textContent = thread.latest_content_redacted
      ? "正文因当前审计角色而隐藏"
      : compactThreadContent(thread.latest_message_summary);

    const markers = document.createElement("span");
    markers.className = "thread-list-markers";
    const markerValues = [];
    if (thread.attachment_count) markerValues.push([`附件 ${thread.attachment_count}`, ""]);
    if (thread.pending_task_count) markerValues.push([`待处理任务 ${thread.pending_task_count}`, ""]);
    if (thread.exception_count) markerValues.push([`异常 ${thread.exception_count}`, "exception"]);
    if (thread.agent_pending_read_count) {
      markerValues.push([`待 Agent 读取 ${thread.agent_pending_read_count}`, ""]);
    }
    (thread.organizations || []).forEach((organization) => {
      markerValues.push([safeText(organization.name), "organization"]);
    });
    if (!markerValues.length) markerValues.push([`${thread.message_count} 条消息`, ""]);
    markerValues.forEach(([label, className]) => {
      const marker = document.createElement("span");
      marker.className = `thread-marker ${className}`.trim();
      marker.textContent = label;
      markers.append(marker);
    });
    button.append(top, participants, preview, markers);
    button.addEventListener("click", () => selectThread(String(thread.thread_id)));
    fragment.append(button);
  });
  elements.threadList.append(fragment);
}

function setThreadDetailEmpty(title, copy) {
  elements.threadDetail.hidden = true;
  elements.threadDetailEmpty.hidden = false;
  const heading = elements.threadDetailEmpty.querySelector("h2");
  const paragraph = elements.threadDetailEmpty.querySelector("p");
  if (heading) heading.textContent = title;
  if (paragraph) paragraph.textContent = copy;
}

function openThreadAgent(agent) {
  const accessible = (state.dashboard?.agents || []).some(
    (candidate) => String(candidate.id) === String(agent.id),
  );
  if (!accessible) {
    return;
  }
  const url = new URL(window.location.href);
  url.searchParams.set("module", "relay");
  url.searchParams.set("view", "agents");
  url.searchParams.set("agent", String(agent.id));
  if (state.selectedThreadId) {
    url.searchParams.set("returnThread", state.selectedThreadId);
  }
  history.pushState({ module: "relay", section: "agents" }, "", `${url.pathname}${url.search}`);
  activateRoute("relay", "agents", { updateHistory: false, focusContent: true });
  const card = document.querySelector(`[data-agent-id="${CSS.escape(String(agent.id))}"]`);
  if (card) {
    card.classList.add("jump-highlight");
    card.scrollIntoView({ behavior: "smooth", block: "center" });
    card.focus({ preventScroll: true });
  }
}

function participantChip(agent) {
  const accessible = (state.dashboard?.agents || []).some(
    (candidate) => String(candidate.id) === String(agent.id),
  );
  const item = document.createElement(accessible ? "button" : "span");
  item.className = "thread-participant-chip";
  if (accessible) {
    item.type = "button";
    item.title = "在云驿查看这个 Agent";
    item.addEventListener("click", () => openThreadAgent(agent));
  } else {
    item.title = "你可以在本对话中识别该 Agent，但没有它的管理入口";
  }
  const label = document.createElement("span");
  label.textContent = `${agentDisplayName(agent)} · ${agentTypeLabel(agent)}`;
  item.append(agentAvatar(agent), label);
  return item;
}

function renderThreadMessageContent(message, body) {
  const format = document.createElement("p");
  format.className = "thread-content-format";
  format.textContent = message.content_redacted
    ? "审计角色 · 正文已隐藏"
    : message.content_format === "markdown"
    ? "Markdown · 当前以安全纯文本显示"
    : message.content_format === "json"
    ? "JSON · 安全原始视图"
    : "纯文本";
  const content = document.createElement("pre");
  content.textContent = message.content_redacted
    ? "正文因当前审计角色而隐藏。"
    : safeText(message.content_body, "无正文");
  body.append(format, content);
}

function appendThreadTaskCard(message, body) {
  if (message.message_type !== "task" && message.message_type !== "result") {
    return;
  }
  const card = document.createElement("section");
  card.className = "thread-task-card";
  const heading = document.createElement("strong");
  heading.textContent = message.message_type === "result" ? "任务结果" : "任务信息";
  const grid = document.createElement("div");
  grid.className = "thread-task-grid";
  const fields = message.message_type === "result"
    ? [["结果摘要", message.result_summary || "结果正文见下方"]]
    : [
      ["指令", message.task_instruction || (message.content_redacted ? "已隐藏" : "未提供")],
      ["期望输出", message.task_expected_output || "未提供"],
      ["优先级", statusLabel(message.priority)],
      ["需要确认收到", message.requires_ack ? "是" : "否"],
      ["截止时间", message.task_deadline ? dateText(message.task_deadline) : "未设置"],
    ];
  fields.forEach(([label, value]) => {
    const field = document.createElement("span");
    field.className = "thread-task-field";
    const name = document.createElement("span");
    name.textContent = label;
    const detail = document.createElement("strong");
    detail.textContent = safeText(value);
    field.append(name, detail);
    grid.append(field);
  });
  card.append(heading, grid);
  body.append(card);
}

function appendThreadAttachments(message, body) {
  if (!Array.isArray(message.attachments) || !message.attachments.length) {
    return;
  }
  const list = document.createElement("div");
  list.className = "thread-attachment-list";
  message.attachments.forEach((attachment) => {
    const card = document.createElement("article");
    card.className = "thread-attachment-card";
    const name = document.createElement("strong");
    name.textContent = safeText(attachment.filename, "未命名附件");
    const info = document.createElement("span");
    info.textContent = `${safeText(attachment.content_type, "未知类型")} · ${formatFileSize(attachment.size)}`;
    const pending = document.createElement("span");
    pending.textContent = "安全预览与授权下载将在附件切片接入";
    card.append(name, info, pending);
    list.append(card);
  });
  body.append(list);
}

function renderTimelineEvent(message) {
  const event = document.createElement("article");
  event.className = "timeline-event";
  event.id = `message-${message.message_id}`;
  event.tabIndex = -1;
  const heading = document.createElement("strong");
  heading.textContent = `${messageTypeLabel(message.message_type)} · ${safeText(message.subject, "无主题事件")}`;
  const route = document.createElement("span");
  route.textContent = `${agentDisplayName(message.sender)} → ${agentDisplayName(message.recipient)} · ${dateText(message.created_at)}`;
  const content = document.createElement("span");
  content.textContent = message.content_redacted
    ? "事件内容因当前审计角色而隐藏。"
    : compactThreadContent(message.content_body, "没有附加说明");
  event.append(heading, route, content);
  return event;
}

function renderTimelineMessage(message, messagesById, repliedMessageIds) {
  if (["event", "system", "error"].includes(message.message_type)) {
    return renderTimelineEvent(message);
  }
  const card = document.createElement("article");
  card.className = "message-card thread-message";
  card.id = `message-${message.message_id}`;
  card.tabIndex = -1;
  card.style.setProperty("--agent-hue", String(agentHue(message.sender)));
  const body = document.createElement("div");
  body.className = "thread-message-body";
  const identity = document.createElement("div");
  identity.className = "thread-message-identity";
  const sender = document.createElement("strong");
  sender.textContent = agentDisplayName(message.sender);
  const type = document.createElement("span");
  type.className = "thread-agent-type";
  type.textContent = `${agentTypeLabel(message.sender)} · ${messageTypeLabel(message.message_type)}`;
  const time = document.createElement("span");
  time.className = "thread-message-time";
  time.textContent = dateText(message.created_at);
  identity.append(sender, type, time);
  const route = document.createElement("div");
  route.className = "thread-message-route";
  route.textContent = `发送给 ${agentDisplayName(message.recipient)} · ${agentTypeLabel(message.recipient)}`;
  const subject = document.createElement("strong");
  subject.className = "thread-message-subject";
  subject.textContent = safeText(message.subject, "无主题消息");
  body.append(identity, route, subject);

  const states = document.createElement("div");
  states.className = "thread-message-states";
  const communication = document.createElement("span");
  communication.className = "thread-state-group";
  communication.append(document.createTextNode("通信状态"), chip(message.communication_state));
  states.append(communication);
  if (repliedMessageIds.has(message.message_id)) {
    const replied = document.createElement("span");
    replied.className = "thread-state-group";
    replied.append(document.createTextNode("后续状态"), chip("replied"));
    states.append(replied);
  }
  if (message.work_state) {
    const work = document.createElement("span");
    work.className = "thread-state-group";
    work.append(document.createTextNode("工作状态"), chip(message.work_state));
    states.append(work);
  }
  body.append(states);

  if (message.reply_to) {
    const parent = messagesById.get(message.reply_to);
    const reference = document.createElement("button");
    reference.type = "button";
    reference.className = "thread-reply-reference";
    reference.textContent = parent
      ? `回复 ${agentDisplayName(parent.sender)}：${safeText(parent.subject, "无主题消息")}`
      : "被回复的消息已不在当前可见范围";
    reference.disabled = !parent;
    if (parent) {
      reference.addEventListener("click", () => {
        const target = document.querySelector(`#message-${CSS.escape(String(parent.message_id))}`);
        target?.scrollIntoView({ behavior: "smooth", block: "center" });
        target?.focus({ preventScroll: true });
        target?.classList.add("jump-highlight");
        window.setTimeout(() => target?.classList.remove("jump-highlight"), 1400);
      });
    }
    body.append(reference);
  }
  appendThreadTaskCard(message, body);
  renderThreadMessageContent(message, body);
  appendThreadAttachments(message, body);

  const footer = document.createElement("div");
  footer.className = "message-footer";
  const trust = document.createElement("span");
  trust.textContent = message.security_label === "external_agent_content"
    ? "来自 Agent 的不可信外部内容"
    : safeText(message.security_label);
  const identifier = document.createElement("span");
  identifier.textContent = safeText(message.message_id);
  footer.append(trust, identifier);
  body.append(footer);
  card.append(agentAvatar(message.sender, "agent-timeline-avatar"), body);
  return card;
}

function renderThreadDetail(thread) {
  state.selectedThread = thread;
  elements.threadDetailEmpty.hidden = true;
  elements.threadDetail.hidden = false;
  elements.threadDetailTopic.textContent = safeText(thread.topic, "无主题对话");
  elements.threadDetailParticipants.replaceChildren();
  (thread.participants || []).forEach((agent) => {
    elements.threadDetailParticipants.append(participantChip(agent));
  });
  (thread.organizations || []).forEach((organization) => {
    const label = document.createElement("span");
    label.className = "thread-marker organization";
    label.textContent = safeText(organization.name);
    elements.threadDetailParticipants.append(label);
  });
  elements.messageList.replaceChildren();
  const messages = Array.isArray(thread.messages) ? thread.messages : [];
  const messagesById = new Map(messages.map((message) => [message.message_id, message]));
  const repliedMessageIds = new Set(messages.map((message) => message.reply_to).filter(Boolean));
  let lastDate = "";
  messages.forEach((message) => {
    const parsed = new Date(message.created_at);
    const dateKey = Number.isNaN(parsed.getTime()) ? safeText(message.created_at) : parsed.toDateString();
    if (dateKey !== lastDate) {
      const separator = document.createElement("div");
      separator.className = "thread-date-separator";
      separator.textContent = Number.isNaN(parsed.getTime())
        ? safeText(message.created_at)
        : new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "long", day: "numeric" }).format(parsed);
      elements.messageList.append(separator);
      lastDate = dateKey;
    }
    elements.messageList.append(renderTimelineMessage(message, messagesById, repliedMessageIds));
  });
  document.title = `星云驿 · ${safeText(thread.topic, "对话")}`;
}

async function loadThreadDetail(threadId) {
  setThreadDetailEmpty("正在读取对话", "只会读取当前 Human 有权查看的 Thread，不会改变 Agent read 或 ACK 状态。");
  try {
    const thread = await requestJson(`/api/v1/orbit/threads/${encodeURIComponent(threadId)}`);
    if (state.selectedThreadId !== String(threadId)) {
      return;
    }
    renderThreadDetail(thread);
  } catch (error) {
    if (state.selectedThreadId !== String(threadId)) {
      return;
    }
    state.selectedThread = null;
    setThreadDetailEmpty(
      "无法打开这条对话",
      error.status === 404
        ? "对话已不存在，或已从你的当前授权范围移除。"
        : "对话读取失败，请稍后刷新重试。",
    );
  }
}

async function selectThread(threadId, { updateHistory = true } = {}) {
  state.selectedThreadId = String(threadId);
  state.selectedThread = null;
  updateThreadWorkspaceMode();
  renderThreadList();
  if (updateHistory) {
    history.pushState({ module: "orbit", section: "communications", thread: threadId }, "", threadRouteUrl());
  }
  await loadThreadDetail(threadId);
  elements.threadDetailTopic.focus?.({ preventScroll: true });
}

function clearThreadSelection({ updateHistory = true } = {}) {
  state.selectedThreadId = "";
  state.selectedThread = null;
  updateThreadWorkspaceMode();
  renderThreadList();
  setThreadDetailEmpty("选择一条协作对话", "同一组 Agent 的不同话题会保持为不同 Thread，不会错误合并。");
  if (updateHistory) {
    history.pushState({ module: "orbit", section: "communications" }, "", threadRouteUrl());
  }
}

function threadListEndpoint() {
  const parameters = new URLSearchParams({ limit: "200" });
  if (state.threadQuery) {
    parameters.set("query", state.threadQuery);
  }
  return `/api/v1/orbit/threads?${parameters.toString()}`;
}

async function loadThreads({ loadSelection = true } = {}) {
  const threads = await requestJson(threadListEndpoint());
  state.threads = Array.isArray(threads) ? threads : [];
  renderThreadOrganizationOptions();
  renderThreadList();
  if (loadSelection && state.selectedThreadId) {
    await loadThreadDetail(state.selectedThreadId);
  } else if (!state.selectedThreadId) {
    setThreadDetailEmpty("选择一条协作对话", "同一组 Agent 的不同话题会保持为不同 Thread，不会错误合并。");
  }
}

function renderSecurity(security) {
  const password = security.password_configured ? "密码已设置" : "需先找回账户设置密码";
  const mfa = security.mfa_enabled ? "MFA 已启用" : "MFA 未启用";
  const keys = `${safeText(security.active_human_keys, "0")} 个兼容 Key`;
  elements.securityStatus.textContent = `${password} · ${mfa} · ${keys}`;
  elements.openMfa.disabled = !security.password_configured;
  elements.openKeyRotation.disabled = !security.password_configured;
  elements.ssoSecurityCard.hidden = !Boolean(state.authConfig?.enterprise_oidc_enabled);
  elements.openSsoLink.disabled = !security.password_configured;
}

function closeSsoLinkDialog() {
  elements.ssoLinkPassword.value = "";
  elements.ssoLinkMfa.value = "";
  elements.ssoLinkProvider.replaceChildren();
  elements.ssoLinkResult.textContent = "";
  if (elements.ssoLinkDialog.open) {
    elements.ssoLinkDialog.close();
  }
}

async function openSsoLinkDialog() {
  elements.ssoLinkProvider.replaceChildren();
  elements.ssoLinkResult.textContent = "正在查找当前邮箱可用的企业 SSO…";
  elements.ssoLinkDialog.showModal();
  try {
    const email = state.dashboard?.user?.email || "";
    const discovered = await requestJson("/api/v1/auth/oidc/providers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    const providers = Array.isArray(discovered.items) ? discovered.items : [];
    providers.forEach((provider) => {
      const option = document.createElement("option");
      option.value = String(provider.provider_id);
      option.dataset.organizationId = String(provider.organization_id);
      option.textContent = `${safeText(provider.display_name)} · ${safeText(provider.issuer)}`;
      elements.ssoLinkProvider.append(option);
    });
    elements.ssoLinkResult.textContent = providers.length
      ? "请选择身份提供方并重新验证当前账户。"
      : "当前邮箱域名尚未配置企业 SSO。";
    elements.ssoLinkResult.className = `form-status ${providers.length ? "" : "error"}`.trim();
  } catch (error) {
    elements.ssoLinkResult.textContent = error.message;
    elements.ssoLinkResult.className = "form-status error";
  }
}

async function linkEnterpriseOidc(event) {
  event.preventDefault();
  const option = elements.ssoLinkProvider.selectedOptions[0];
  if (!option) {
    elements.ssoLinkResult.textContent = "没有可绑定的企业身份提供方。";
    elements.ssoLinkResult.className = "form-status error";
    return;
  }
  const proof = mfaProof(elements.ssoLinkMfa.value);
  const submit = elements.ssoLinkForm.querySelector("button[type='submit']");
  submit.disabled = true;
  try {
    const started = await requestJson(
      `/api/v1/orbit/organizations/${encodeURIComponent(option.dataset.organizationId)}/oidc-providers/${encodeURIComponent(option.value)}/link`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": state.csrfToken },
        body: JSON.stringify({
          password: elements.ssoLinkPassword.value,
          ...proof,
        }),
      },
    );
    elements.ssoLinkPassword.value = "";
    elements.ssoLinkMfa.value = "";
    const authorizationUrl = new URL(started.authorization_url);
    if (!["https:", "http:"].includes(authorizationUrl.protocol)) {
      throw new Error("企业 SSO 返回了不安全的授权地址。" );
    }
    window.location.assign(authorizationUrl.href);
  } catch (error) {
    elements.ssoLinkPassword.value = "";
    elements.ssoLinkMfa.value = "";
    elements.ssoLinkResult.textContent = error.message;
    elements.ssoLinkResult.className = "form-status error";
    submit.disabled = false;
  }
}

function renderDashboard(dashboard) {
  state.dashboard = dashboard;
  const user = dashboard.user || {};
  const organizations = Array.isArray(dashboard.organizations) ? dashboard.organizations : [];
  const agents = Array.isArray(dashboard.agents) ? dashboard.agents : [];
  const tasks = Array.isArray(dashboard.tasks) ? dashboard.tasks : [];
  const approvals = Array.isArray(dashboard.approvals) ? dashboard.approvals : [];
  elements.humanName.textContent = safeText(user.display_name, "星轨用户");
  elements.humanEmail.textContent = safeText(user.email);
  elements.humanAvatar.textContent = safeText(user.display_name, "星").slice(0, 1);
  elements.profileName.textContent = safeText(user.display_name, "未设置");
  elements.profileEmail.textContent = safeText(user.email);
  elements.profileTimezone.textContent = safeText(
    Intl.DateTimeFormat().resolvedOptions().timeZone,
    "此设备未提供",
  );
  renderMetrics(dashboard.metrics || {}, agents, organizations);
  renderOrganizations(organizations);
  renderAgents(agents);
  renderTasks(tasks);
  renderApprovals(approvals);
}

async function loadDashboard() {
  elements.refresh.disabled = true;
  setConnection("正在同步数据", "loading");
  try {
    const [dashboard, connectors, security, threads] = await Promise.all([
      requestJson("/api/v1/orbit/dashboard"),
      requestJson("/api/v1/orbit/connectors"),
      requestJson("/api/v1/orbit/security"),
      requestJson(threadListEndpoint()),
    ]);
    state.connectors = Array.isArray(connectors.items) ? connectors.items : [];
    state.threads = Array.isArray(threads) ? threads : [];
    renderDashboard(dashboard);
    renderConnectors(state.connectors);
    renderSecurity(security);
    renderThreadOrganizationOptions();
    renderThreadList();
    if (state.selectedThreadId) {
      await loadThreadDetail(state.selectedThreadId);
    } else {
      setThreadDetailEmpty("选择一条协作对话", "同一组 Agent 的不同话题会保持为不同 Thread，不会错误合并。");
    }
    elements.welcomeView.hidden = true;
    elements.workspaceView.hidden = false;
    setConnection("数据已同步", "success");
    await maybeOpenRequestedPairing();
    await maybeAcceptOrganizationInvitation();
  } catch (error) {
    setConnection("数据同步失败", "error");
    throw error;
  } finally {
    elements.refresh.disabled = false;
  }
}

async function loadAuthConfig() {
  try {
    state.authConfig = await requestJson("/api/v1/auth/config");
  } catch (_error) {
    state.authConfig = {
      self_service_enabled: false,
      open_registration_enabled: false,
      codex_setup_platforms: [],
      connector_release: FALLBACK_CONNECTOR_RELEASE,
      managed_agent_domain: "agents.local",
    };
  }
  elements.pairingAddressDomain.textContent = `@${managedAgentDomain()}`;
  const selfService = Boolean(state.authConfig.self_service_enabled);
  elements.loginForm.hidden = !selfService;
  elements.openRecovery.hidden = !selfService;
  elements.openRegister.hidden = !Boolean(state.authConfig.open_registration_enabled);
  elements.oidcEntry.hidden = !Boolean(state.authConfig.enterprise_oidc_enabled);
  elements.legacyEntry.open = !selfService;
}

async function discoverEnterpriseOidc() {
  const email = elements.loginEmail.value.trim();
  elements.oidcOptions.replaceChildren();
  if (!email || !email.includes("@")) {
    setFormStatus("请先填写企业邮箱，再选择企业 SSO。", "error");
    elements.loginEmail.focus();
    return;
  }
  elements.discoverOidc.disabled = true;
  setFormStatus("正在查找已验证的企业身份提供方…");
  try {
    const discovered = await requestJson("/api/v1/auth/oidc/providers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    const providers = Array.isArray(discovered.items) ? discovered.items : [];
    if (providers.length === 0) {
      setFormStatus("该邮箱域名尚未配置企业 SSO。", "error");
      return;
    }
    providers.forEach((provider) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "quiet-button";
      button.textContent = `通过 ${safeText(provider.display_name, "企业 SSO")} 登录`;
      button.addEventListener("click", async () => {
        button.disabled = true;
        try {
          const started = await requestJson(
            `/api/v1/auth/oidc/${encodeURIComponent(provider.provider_id)}/start`,
            { method: "POST" },
          );
          const authorizationUrl = new URL(started.authorization_url);
          if (!['https:', 'http:'].includes(authorizationUrl.protocol)) {
            throw new Error("企业 SSO 返回了不安全的授权地址。");
          }
          window.location.assign(authorizationUrl.href);
        } catch (error) {
          button.disabled = false;
          setFormStatus(error.message, "error");
        }
      });
      elements.oidcOptions.append(button);
    });
    setFormStatus("请选择企业身份提供方继续。", "success");
  } catch (error) {
    setFormStatus(error.message, "error");
  } finally {
    elements.discoverOidc.disabled = false;
  }
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
    closeOrganizationCreateDialog();
    closeOrganizationManagement();
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
elements.discoverOidc.addEventListener("click", discoverEnterpriseOidc);
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
elements.profileRefresh.addEventListener("click", async () => {
  try {
    await loadDashboard();
  } catch (error) {
    setConnection(error.message, "error");
  }
});
elements.profileSignOut.addEventListener("click", signOut);
elements.threadSearchInput.addEventListener("input", () => {
  state.threadQuery = elements.threadSearchInput.value.trim();
  state.selectedThreadId = "";
  state.selectedThread = null;
  updateThreadWorkspaceMode();
  setThreadDetailEmpty("选择一条协作对话", "搜索结果只包含当前 Human 有权查看的内容。");
  history.replaceState(
    { module: "orbit", section: "communications" },
    "",
    threadRouteUrl(),
  );
  window.clearTimeout(state.threadSearchTimer);
  state.threadSearchTimer = window.setTimeout(async () => {
    try {
      await loadThreads({ loadSelection: false });
    } catch (_error) {
      elements.threadList.replaceChildren(emptyState("搜索暂时不可用，请稍后重试。"));
    }
  }, 260);
});
elements.threadOrganizationFilter.addEventListener("change", () => {
  state.threadOrganization = elements.threadOrganizationFilter.value;
  if (!visibleThreadSummaries().some(
    (thread) => String(thread.thread_id) === state.selectedThreadId,
  )) {
    state.selectedThreadId = "";
    state.selectedThread = null;
    setThreadDetailEmpty("选择一条协作对话", "当前列表已按组织范围筛选。");
  }
  updateThreadWorkspaceMode();
  renderThreadList();
  history.replaceState(
    { module: "orbit", section: "communications", thread: state.selectedThreadId || null },
    "",
    threadRouteUrl(),
  );
});
elements.threadFilters.forEach((button) => {
  button.addEventListener("click", () => {
    if (button.getAttribute("aria-disabled") === "true") {
      return;
    }
    state.threadFilter = button.dataset.threadFilter || "all";
    elements.threadFilters.forEach((item) => {
      const active = item === button;
      item.classList.toggle("active", active);
      if (item.getAttribute("aria-disabled") !== "true") {
        item.setAttribute("aria-pressed", String(active));
      }
    });
    if (!visibleThreadSummaries().some(
      (thread) => String(thread.thread_id) === state.selectedThreadId,
    )) {
      state.selectedThreadId = "";
      state.selectedThread = null;
      setThreadDetailEmpty("选择一条协作对话", "当前列表已按真实异常状态筛选。");
    }
    updateThreadWorkspaceMode();
    renderThreadList();
    history.replaceState(
      { module: "orbit", section: "communications", thread: state.selectedThreadId || null },
      "",
      threadRouteUrl(),
    );
  });
});
elements.threadList.addEventListener("keydown", (event) => {
  if (!["ArrowDown", "ArrowUp"].includes(event.key)) {
    return;
  }
  const items = Array.from(elements.threadList.querySelectorAll(".thread-list-item"));
  const index = items.indexOf(document.activeElement);
  if (index < 0 || items.length < 2) {
    return;
  }
  event.preventDefault();
  const direction = event.key === "ArrowDown" ? 1 : -1;
  items[(index + direction + items.length) % items.length].focus();
});
elements.threadMobileBack.addEventListener("click", () => clearThreadSelection());
elements.threadLatest.addEventListener("click", () => {
  elements.messageList.lastElementChild?.scrollIntoView({ behavior: "smooth", block: "end" });
});
elements.approvalForm.addEventListener("submit", decideApproval);
elements.approvalClose.addEventListener("click", closeApprovalDialog);
elements.approvalCancel.addEventListener("click", closeApprovalDialog);
elements.approvalDialog.addEventListener("close", closeApprovalDialog);
elements.openPairing.addEventListener("click", () => openPairingDialog());
elements.pairingHostCards.forEach((button) => {
  button.addEventListener("click", () => selectPairingHost(button.dataset.connectorType));
});
elements.pairingCopyPrompt.addEventListener("click", copyPairingPrompt);
elements.pairingGuideBack.addEventListener("click", () => showPairingGuide());
elements.pairingGuideCancel.addEventListener("click", () => closePairingDialog());
elements.pairingForm.addEventListener("submit", decidePairing);
elements.pairingDeny.addEventListener("click", (event) => decidePairing(event, "denied"));
elements.pairingClose.addEventListener("click", () => closePairingDialog());
elements.pairingCancel.addEventListener("click", () => closePairingDialog());
elements.pairingDialog.addEventListener("close", () => closePairingDialog());
elements.handleForm.addEventListener("submit", saveAgentHandle);
elements.handleClose.addEventListener("click", closeHandleDialog);
elements.handleCancel.addEventListener("click", closeHandleDialog);
elements.handleDialog.addEventListener("close", closeHandleDialog);
elements.pairingId.addEventListener("change", loadPairingPreview);
elements.pairingTargetMode.addEventListener("change", updatePairingTargetMode);
elements.pairingExistingAgent.addEventListener("change", () => {
  if (state.pairingTargetResolution !== "ambiguous") {
    return;
  }
  state.pairingCreateNewAutomatically = elements.pairingExistingAgent.value === "__create_new__";
  elements.pairingTargetMode.value = state.pairingCreateNewAutomatically ? "new" : "existing";
});
elements.pairingLocalId.addEventListener("change", () => {
  elements.pairingLocalId.value = canonicalPairingLocalId(elements.pairingLocalId.value);
});
elements.revokeForm.addEventListener("submit", revokeConnector);
elements.revokeClose.addEventListener("click", closeRevokeDialog);
elements.revokeCancel.addEventListener("click", closeRevokeDialog);
elements.revokeDialog.addEventListener("close", closeRevokeDialog);
elements.deleteAgentForm.addEventListener("submit", deleteAgent);
elements.deleteAgentClose.addEventListener("click", closeDeleteAgentDialog);
elements.deleteAgentCancel.addEventListener("click", closeDeleteAgentDialog);
elements.deleteAgentDialog.addEventListener("close", closeDeleteAgentDialog);
elements.openOrganizationCreate.addEventListener("click", () => {
  elements.organizationCreateResult.textContent = "创建后你将成为首位 Owner。";
  elements.organizationCreateDialog.showModal();
  elements.organizationName.focus();
});
elements.organizationCreateForm.addEventListener("submit", createOrganization);
elements.organizationCreateClose.addEventListener("click", closeOrganizationCreateDialog);
elements.organizationCreateCancel.addEventListener("click", closeOrganizationCreateDialog);
elements.organizationCreateDialog.addEventListener("close", closeOrganizationCreateDialog);
elements.organizationInviteForm.addEventListener("submit", inviteOrganizationMember);
elements.organizationManageClose.addEventListener("click", closeOrganizationManagement);
elements.organizationManageCancel.addEventListener("click", closeOrganizationManagement);
elements.organizationManageDialog.addEventListener("close", closeOrganizationManagement);
elements.organizationLeave.addEventListener("click", leaveOrganization);
elements.organizationDomainAdd.addEventListener("click", addOrganizationDomain);
elements.organizationOidcAdd.addEventListener("click", addOrganizationOidcProvider);
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
elements.openSsoLink.addEventListener("click", openSsoLinkDialog);
elements.ssoLinkForm.addEventListener("submit", linkEnterpriseOidc);
elements.ssoLinkClose.addEventListener("click", closeSsoLinkDialog);
elements.ssoLinkCancel.addEventListener("click", closeSsoLinkDialog);
elements.ssoLinkDialog.addEventListener("close", closeSsoLinkDialog);

window.addEventListener("popstate", () => {
  const parameters = new URLSearchParams(window.location.search);
  const previousQuery = state.threadQuery;
  applyThreadRouteParameters(parameters);
  activateRoute(parameters.get("module") || "orbit", parameters.get("view") || "", {
    updateHistory: false,
  });
  renderThreadList();
  if (state.activeModule === "orbit" && state.activeSection === "communications") {
    if (previousQuery !== state.threadQuery) {
      void loadThreads();
    } else if (state.selectedThreadId) {
      void loadThreadDetail(state.selectedThreadId);
    } else {
      setThreadDetailEmpty("选择一条协作对话", "同一组 Agent 的不同话题会保持为不同 Thread，不会错误合并。");
    }
  }
});

window.addEventListener("pagehide", () => {
  clearSensitiveInputs();
  state.csrfToken = "";
  state.pendingOrganizationInvitation = "";
  state.organizationDomainProofs.clear();
});

async function initializeOrbit() {
  initializeWorkspaceNavigation();
  const hashParameters = new URLSearchParams(window.location.hash.replace(/^#/, ""));
  state.pendingOrganizationInvitation = hashParameters.get("organization-invitation") || "";
  history.replaceState(
    { module: state.activeModule, section: state.activeSection },
    "",
    routeUrl(state.activeModule, state.activeSection),
  );
  await loadAuthConfig();
  await restoreSession();
}

initializeOrbit();
