"use strict";

const FALLBACK_CONNECTOR_RELEASE = Object.freeze({
  version: "0.1.0",
  wheel_url: "https://agentpost.me/downloads/agentpost-0.1.0-py3-none-any.whl",
  wheel_sha256: "1fc3f42e8c1141ce65481778587544fc9bf441438c852c0332594ab24a75fdf7",
});
const LOCAL_AGENT_ID_PATTERN = /^[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?$/;
const RESERVED_AGENT_HANDLES = new Set([
  "admin", "agentpost", "api", "app", "connect", "directory", "help", "inbox",
  "login", "logout", "mcp", "orbit", "root", "security", "settings", "signup",
  "support", "system", "www",
]);

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
  pairingSuggestedHandle: "",
  connectors: [],
  threads: [],
  selectedThread: null,
  selectedThreadId: "",
  threadFilter: "all",
  threadQuery: "",
  threadOrganization: "",
  threadSearchTimer: null,
  threadBrowserExpanded: true,
  selectedAgentId: "",
  selectedAgent: null,
  agentTab: "summary",
  agentQuery: "",
  agentRelatedThreads: [],
  activeModule: "orbit",
  activeSection: "communications",
  lastSectionByModule: {
    orbit: "communications",
    relay: "agents",
    settings: "profile",
  },
};

const elements = {
  welcomeView: document.querySelector("#welcome-view"),
  workspaceView: document.querySelector("#workspace-view"),
  loginForm: document.querySelector("#login-form"),
  loginEmail: document.querySelector("#login-email"),
  loginPassword: document.querySelector("#login-password"),
  loginMfa: document.querySelector("#login-mfa"),
  oidcEntry: document.querySelector("#oidc-entry"),
  discoverOidc: document.querySelector("#discover-oidc"),
  oidcOptions: document.querySelector("#oidc-options"),
  openRegister: document.querySelector("#open-register"),
  openRecovery: document.querySelector("#open-recovery"),
  accessResult: document.querySelector("#access-result"),
  connectionState: document.querySelector("#connection-state"),
  brandSection: document.querySelector("#brand-section"),
  topHumanName: document.querySelector("#top-human-name"),
  topHumanAvatar: document.querySelector("#top-human-avatar"),
  refresh: document.querySelector("#refresh-dashboard"),
  signOut: document.querySelector("#sign-out"),
  profileRefresh: document.querySelector("#profile-refresh"),
  profileSignOut: document.querySelector("#profile-sign-out"),
  humanName: document.querySelector("#human-name"),
  humanEmail: document.querySelector("#human-email"),
  humanAvatar: document.querySelector("#human-avatar"),
  approvalQuickCount: document.querySelector("#approval-quick-count"),
  taskQuickCount: document.querySelector("#task-quick-count"),
  approvalMobileCount: document.querySelector("#approval-mobile-count"),
  taskMobileCount: document.querySelector("#task-mobile-count"),
  profileName: document.querySelector("#profile-name"),
  profileUsername: document.querySelector("#profile-username"),
  profileEmail: document.querySelector("#profile-email"),
  profileTimezone: document.querySelector("#profile-timezone"),
  primaryNavigation: document.querySelector("#primary-navigation"),
  primaryNavigationItems: Array.from(document.querySelectorAll(".primary-nav-item")),
  contextNavigation: document.querySelector("#context-navigation"),
  orbitMobileShortcuts: document.querySelector("#orbit-mobile-shortcuts"),
  contextNavigationGroups: Array.from(document.querySelectorAll("[data-context-module]")),
  contextNavigationItems: Array.from(document.querySelectorAll(".context-nav-item")),
  moduleViews: Array.from(document.querySelectorAll(".module-view")),
  contextEyebrow: document.querySelector("#context-eyebrow"),
  contextTitle: document.querySelector("#context-title"),
  contextCopy: document.querySelector("#context-copy"),
  threadBrowser: document.querySelector("#thread-browser"),
  threadParentToggle: document.querySelector("#thread-parent-toggle"),
  threadParentSummary: document.querySelector("#thread-parent-summary"),
  threadUnreadCount: document.querySelector("#thread-unread-count"),
  threadCount: document.querySelector("#thread-count"),
  threadSearchInput: document.querySelector("#thread-search-input"),
  threadOrganizationFilter: document.querySelector("#thread-organization-filter"),
  threadFilters: Array.from(document.querySelectorAll("[data-thread-filter]")),
  threadArchiveLibrary: document.querySelector("#thread-archive-library"),
  threadList: document.querySelector("#thread-list"),
  threadMobileBack: document.querySelector("#thread-mobile-back"),
  threadDetailEmpty: document.querySelector("#thread-detail-empty"),
  threadDetail: document.querySelector("#thread-detail"),
  threadDetailTopic: document.querySelector("#thread-detail-topic"),
  threadDetailCount: document.querySelector("#thread-detail-count"),
  threadDetailRoute: document.querySelector("#thread-detail-route"),
  threadDetailState: document.querySelector("#thread-detail-state"),
  threadDetailParticipants: document.querySelector("#thread-detail-participants"),
  threadArchive: document.querySelector("#thread-archive"),
  threadLatest: document.querySelector("#thread-latest"),
  threadArchiveDialog: document.querySelector("#thread-archive-dialog"),
  threadArchiveForm: document.querySelector("#thread-archive-form"),
  threadArchiveClose: document.querySelector("#thread-archive-close"),
  threadArchiveCancel: document.querySelector("#thread-archive-cancel"),
  threadArchiveSummary: document.querySelector("#thread-archive-summary"),
  threadArchiveId: document.querySelector("#thread-archive-id"),
  threadArchiveResult: document.querySelector("#thread-archive-result"),
  threadArchiveSubmit: document.querySelector("#thread-archive-submit"),
  agentBrowser: document.querySelector("#agent-browser"),
  agentBrowserCount: document.querySelector("#agent-browser-count"),
  agentSearchInput: document.querySelector("#agent-search-input"),
  agentBrowserNew: document.querySelector("#agent-browser-new"),
  agentBrowserList: document.querySelector("#agent-browser-list"),
  agentMobileBack: document.querySelector("#agent-mobile-back"),
  agentOverview: document.querySelector("#agent-overview"),
  agentOverviewNew: document.querySelector("#agent-overview-new"),
  agentStatAll: document.querySelector("#agent-stat-all"),
  agentStatConnected: document.querySelector("#agent-stat-connected"),
  agentStatAwaiting: document.querySelector("#agent-stat-awaiting"),
  agentStatOffline: document.querySelector("#agent-stat-offline"),
  agentStatError: document.querySelector("#agent-stat-error"),
  agentOverviewGroups: document.querySelector("#agent-overview-groups"),
  agentDetail: document.querySelector("#agent-detail"),
  agentDetailMissing: document.querySelector("#agent-detail-missing"),
  agentDetailAvatar: document.querySelector("#agent-detail-avatar"),
  agentDetailName: document.querySelector("#agent-detail-name"),
  agentDetailSubtitle: document.querySelector("#agent-detail-subtitle"),
  agentDetailStatus: document.querySelector("#agent-detail-status"),
  agentReturnThread: document.querySelector("#agent-return-thread"),
  agentDetailTabs: Array.from(document.querySelectorAll("[data-agent-tab]")),
  agentDetailPanels: Array.from(document.querySelectorAll("[data-agent-panel]")),
  agentDetailSummary: document.querySelector("#agent-detail-summary"),
  agentCurrentConnection: document.querySelector("#agent-current-connection"),
  agentDetailCapabilities: document.querySelector("#agent-detail-capabilities"),
  agentDetailAccess: document.querySelector("#agent-detail-access"),
  agentConnectionHistory: document.querySelector("#agent-connection-history"),
  agentRelatedThreads: document.querySelector("#agent-related-threads"),
  agentOwnerActions: document.querySelector("#agent-owner-actions"),
  agentReadonlyActions: document.querySelector("#agent-readonly-actions"),
  agentReconnect: document.querySelector("#agent-reconnect"),
  agentRename: document.querySelector("#agent-rename"),
  agentSetDefault: document.querySelector("#agent-set-default"),
  agentDisconnect: document.querySelector("#agent-disconnect"),
  agentDelete: document.querySelector("#agent-delete"),
  organizationCount: document.querySelector("#organization-count"),
  organizationList: document.querySelector("#organization-list"),
  organizationPendingSection: document.querySelector("#organization-pending-section"),
  organizationPendingList: document.querySelector("#organization-pending-list"),
  openOrganizationCreate: document.querySelector("#open-organization-create"),
  taskList: document.querySelector("#task-list"),
  approvalList: document.querySelector("#approval-list"),
  messageList: document.querySelector("#message-list"),
  attachmentPreviewDialog: document.querySelector("#attachment-preview-dialog"),
  attachmentPreviewTitle: document.querySelector("#attachment-preview-title"),
  attachmentPreviewMeta: document.querySelector("#attachment-preview-meta"),
  attachmentPreviewFrame: document.querySelector("#attachment-preview-frame"),
  attachmentPreviewDownload: document.querySelector("#attachment-preview-download"),
  attachmentPreviewClose: document.querySelector("#attachment-preview-close"),
  attachmentPreviewDone: document.querySelector("#attachment-preview-done"),
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
  pairingHandleHelp: document.querySelector("#pairing-handle-help"),
  pairingExistingAgentField: document.querySelector("#pairing-existing-agent-field"),
  pairingExistingAgent: document.querySelector("#pairing-existing-agent"),
  pairingNewAgentFields: document.querySelector("#pairing-new-agent-fields"),
  pairingLocalId: document.querySelector("#pairing-local-id"),
  pairingAddressDomain: document.querySelector("#pairing-address-domain"),
  pairingDisplayName: document.querySelector("#pairing-display-name"),
  pairingCapabilities: document.querySelector("#pairing-capabilities"),
  pairingAccessKey: document.querySelector("#pairing-access-key"),
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
  registerUsername: document.querySelector("#register-username"),
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
  organizationInvitationDialog: document.querySelector("#organization-invitation-dialog"),
  organizationInvitationForm: document.querySelector("#organization-invitation-form"),
  organizationInvitationClose: document.querySelector("#organization-invitation-close"),
  organizationInvitationCancel: document.querySelector("#organization-invitation-cancel"),
  organizationInvitationSubmit: document.querySelector("#organization-invitation-submit"),
  organizationInvitationName: document.querySelector("#organization-invitation-name"),
  organizationInvitationSlug: document.querySelector("#organization-invitation-slug"),
  organizationInvitationRole: document.querySelector("#organization-invitation-role"),
  organizationInvitationExpiry: document.querySelector("#organization-invitation-expiry"),
  organizationInvitationCapability: document.querySelector("#organization-invitation-capability"),
  organizationInvitationVisibility: document.querySelector("#organization-invitation-visibility"),
  organizationInvitationActions: document.querySelector("#organization-invitation-actions"),
  organizationInvitationResult: document.querySelector("#organization-invitation-result"),
  organizationManageDialog: document.querySelector("#organization-manage-dialog"),
  organizationManageTitle: document.querySelector("#organization-manage-title"),
  organizationInviteForm: document.querySelector("#organization-invite-form"),
  organizationManageClose: document.querySelector("#organization-manage-close"),
  organizationManageCancel: document.querySelector("#organization-manage-cancel"),
  organizationManageId: document.querySelector("#organization-manage-id"),
  organizationManageSummary: document.querySelector("#organization-manage-summary"),
  organizationAgentSection: document.querySelector("#organization-agent-section"),
  organizationAgentActions: document.querySelector("#organization-agent-actions"),
  organizationAgentSelect: document.querySelector("#organization-agent-select"),
  organizationAgentPassword: document.querySelector("#organization-agent-password"),
  organizationAgentAdd: document.querySelector("#organization-agent-add"),
  organizationInviteSection: document.querySelector("#organization-invite-section"),
  organizationInviteUsername: document.querySelector("#organization-invite-username"),
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
    title: "我的对话",
    description: "按每个对话查看 Agent 之间的全部往来。",
    defaultSection: "communications",
    sections: Object.freeze(["communications", "tasks", "approvals"]),
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
  ["pairing", "code", "oauth_request"].forEach((name) => url.searchParams.delete(name));
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

function applyAgentRouteParameters(parameters) {
  const allowedTabs = new Set([
    "summary",
    "connection",
    "capabilities",
    "access",
    "history",
    "threads",
    "danger",
  ]);
  state.selectedAgentId = parameters.get("agent") || "";
  state.agentTab = allowedTabs.has(parameters.get("agentTab"))
    ? parameters.get("agentTab")
    : "summary";
  state.agentQuery = parameters.get("agentQuery") || "";
  elements.agentSearchInput.value = state.agentQuery;
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

function agentRouteUrl() {
  const url = new URL(window.location.href);
  url.searchParams.set("module", "relay");
  url.searchParams.set("view", "agents");
  const values = {
    agent: state.selectedAgentId,
    agentTab: state.selectedAgentId && state.agentTab !== "summary" ? state.agentTab : "",
    agentQuery: state.agentQuery,
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
  elements.threadBrowser.hidden = !active || !state.threadBrowserExpanded;
  elements.threadParentToggle?.setAttribute("aria-expanded", String(state.threadBrowserExpanded));
  elements.threadParentToggle?.classList.toggle("expanded", state.threadBrowserExpanded);
}

function updateAgentWorkspaceMode() {
  const active = state.activeModule === "relay" && state.activeSection === "agents";
  elements.workspaceView.classList.toggle("agent-workspace-mode", active);
  elements.workspaceView.classList.toggle(
    "agent-detail-open",
    active && Boolean(state.selectedAgentId),
  );
  elements.agentBrowser.hidden = !active;
}

function isMobileWorkspace() {
  return window.matchMedia("(max-width: 860px)").matches;
}

function resetMobileLayerScroll() {
  if (isMobileWorkspace()) {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }
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
    if (item.classList.contains("orbit-mobile-shortcut")) {
      item.setAttribute("aria-pressed", String(active));
    }
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
  elements.brandSection.textContent = `AgentPost · ${definition.label}`;
  document.title = `星云驿 · ${definition.label}`;
  updateThreadWorkspaceMode();
  updateAgentWorkspaceMode();
  if (routeChanged) {
    resetMobileLayerScroll();
  }
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
  applyAgentRouteParameters(parameters);
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
    item.addEventListener("click", () => {
      if (item === elements.threadParentToggle) {
        const alreadyActive = state.activeModule === "orbit" && state.activeSection === "communications";
        state.threadBrowserExpanded = alreadyActive ? !state.threadBrowserExpanded : true;
      }
      const mobileShortcutIsActive = item.classList.contains("orbit-mobile-shortcut")
        && isMobileWorkspace()
        && state.activeModule === "orbit"
        && state.activeSection === item.dataset.section;
      if (item.classList.contains("orbit-mobile-shortcut") && isMobileWorkspace()) {
        state.threadFilter = "all";
        elements.threadFilters.forEach((filter) => {
          const active = (filter.dataset.threadFilter || "all") === "all";
          filter.classList.toggle("active", active);
          filter.setAttribute("aria-pressed", String(active));
        });
      }
      activateRoute(
        item.dataset.module,
        mobileShortcutIsActive ? "communications" : item.dataset.section,
        { focusContent: true },
      );
      updateThreadWorkspaceMode();
      renderThreadParentSummary();
    });
  });
  [elements.primaryNavigation, elements.contextNavigation, elements.orbitMobileShortcuts].forEach((navigation) => {
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

function setConnection(message, kind = "", compactMessage = message) {
  elements.connectionState.className = `connection ${kind}`.trim();
  const dot = document.createElement("span");
  dot.className = "connection-dot";
  dot.setAttribute("aria-hidden", "true");
  const fullLabel = document.createElement("span");
  fullLabel.className = "connection-label-full";
  fullLabel.textContent = message;
  const compactLabel = document.createElement("span");
  compactLabel.className = "connection-label-compact";
  compactLabel.textContent = compactMessage;
  elements.connectionState.replaceChildren(dot, fullLabel, compactLabel);
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
      return "短名称格式不正确：请使用 1–32 个中文、英文字母或数字；连字符只能放在名称中间且不能连续。";
    }
    if (fields.has("username")) {
      return "用户名格式不正确：请使用 3–32 位小写字母、数字或单个连字符。";
    }
    return "提交内容格式不正确。请检查页面中填写的 Agent 地址、名称和能力标签。";
  }
  if (status === 409 && Array.isArray(error?.details?.suggestions)) {
    return `这个短名称已被使用。可以试试：${error.details.suggestions.join("、")}。`;
  }
  if (status === 409 && String(error?.code || "").toUpperCase() === "USERNAME_ALREADY_REGISTERED") {
    return "这个用户名已被使用，请换一个。";
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
    connected: "在线",
    disconnected: "未连接",
    offline: "离线",
    connection_error: "连接异常",
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

const ORGANIZATION_ROLE_EXPERIENCE = Object.freeze({
  owner: Object.freeze({
    capability: "你可以管理成员、邀请和组织设置。",
    visibility: "可查看明确发到组织协作频道的完整内容，并处理组织 Agent 的审批。个人对话保持私密。",
    actions: "可管理组织、成员和全部角色；不会因此自动拥有、连接或冒充组织 Agent。",
  }),
  admin: Object.freeze({
    capability: "你可以邀请成员并管理日常设置。",
    visibility: "可查看明确发到组织协作频道的完整内容，并处理组织 Agent 的审批。个人对话保持私密。",
    actions: "可邀请和管理 Member/Auditor；不能处置 Owner 或其他受保护管理关系。",
  }),
  member: Object.freeze({
    capability: "你可以查看组织协作，并管理自己的 Agent。",
    visibility: "可查看组织 Agent 和组织协作频道内容；个人对话不会因加入组织而共享。",
    actions: "可把自己拥有的 Agent 加入或移出组织；不能管理其他成员或其他人的 Agent。",
  }),
  auditor: Object.freeze({
    capability: "你可以查看成员、Agent 和协作记录摘要。",
    visibility: "只显示 Agent、消息、任务和审批元数据；正文、附件内容、理由和参数保持隐藏。",
    actions: "不能更改成员、组织设置或 Agent。",
  }),
});

function organizationRoleExperience(role) {
  return ORGANIZATION_ROLE_EXPERIENCE[role] || Object.freeze({
    capability: "组织角色尚未确认",
    visibility: "只显示你当前获准查看的内容。",
    actions: "界面不会根据未知角色开放治理或 Agent 管理操作。",
  });
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
    header.append(identity);

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
      manage.textContent = "查看组织";
      manage.addEventListener("click", () => openOrganizationManagement(organization));
      actions.append(manage);
      card.append(actions);
    }
    fragment.append(card);
  });
  elements.organizationList.append(fragment);
}

function renderPendingOrganizationInvitations(invitations) {
  elements.organizationPendingList.replaceChildren();
  elements.organizationPendingSection.hidden = invitations.length === 0;
  invitations.forEach((invitation) => {
    const card = document.createElement("article");
    card.className = "organization-card";
    const name = document.createElement("strong");
    name.textContent = safeText(invitation.organization_name, invitation.organization_slug);
    const detail = document.createElement("p");
    detail.textContent = `${statusLabel(invitation.role)} · 有效至 ${dateText(invitation.expires_at)}`;
    const description = document.createElement("p");
    description.textContent = safeText(invitation.organization_description, "邀请你加入该组织。加入前不会共享你的个人对话。");
    const actions = document.createElement("div");
    actions.className = "organization-card-actions";
    const accept = document.createElement("button");
    accept.type = "button";
    accept.className = "primary-action";
    accept.textContent = "接受邀请";
    accept.addEventListener("click", () => acceptPendingOrganizationInvitation(invitation, accept));
    actions.append(accept);
    card.append(name, detail, description, actions);
    elements.organizationPendingList.append(card);
  });
}

async function acceptPendingOrganizationInvitation(invitation, button) {
  button.disabled = true;
  try {
    await requestJson(
      `/api/v1/orbit/organization-invitations/${encodeURIComponent(invitation.invitation_id)}/accept`,
      { method: "POST", headers: { "X-CSRF-Token": state.csrfToken } },
    );
    await loadDashboard();
    activateRoute("settings", "organizations", { updateHistory: true });
    setConnection("组织邀请已接受", "success");
  } catch (error) {
    setConnection(error.message, "error");
    button.disabled = false;
  }
}

function eligibleOwnedOrganizationAgents() {
  return (state.dashboard?.agents || []).filter(
    (agent) => agent.role === "owner" && !agent.organization && agent.status === "active",
  );
}

function renderOrganizationAgents(organization) {
  const canManageOwnAgents = ["owner", "admin", "member"].includes(organization.membership_role);
  elements.organizationAgentActions.hidden = !canManageOwnAgents;
  elements.organizationAgentSelect.replaceChildren();
  const eligible = eligibleOwnedOrganizationAgents();
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = eligible.length ? "请选择 Agent" : "没有可加入的自有 Agent";
  elements.organizationAgentSelect.append(placeholder);
  eligible.forEach((agent) => {
    const option = document.createElement("option");
    option.value = String(agent.id);
    option.textContent = `${agentDisplayName(agent)} · ${statusLabel(agent.connection_state)}`;
    elements.organizationAgentSelect.append(option);
  });
  elements.organizationAgentSelect.disabled = !eligible.length;
  elements.organizationAgentAdd.disabled = !eligible.length;
}

async function changeOwnedOrganizationAgent(agent, intent) {
  const organization = state.managedOrganization;
  const selectedAgent = agent || (state.dashboard?.agents || []).find(
    (item) => String(item.id) === elements.organizationAgentSelect.value,
  );
  if (!organization || !selectedAgent) {
    elements.organizationManageResult.textContent = "请先选择一个你拥有的 Agent。";
    elements.organizationManageResult.className = "form-status error";
    return;
  }
  if (intent === "remove" && elements.organizationAgentPassword.value.length < 12) {
    elements.organizationManageResult.textContent = "请输入当前星轨密码后再确认。";
    elements.organizationManageResult.className = "form-status error";
    const passwordDetails = elements.organizationAgentPassword.closest("details");
    if (passwordDetails) {
      passwordDetails.open = true;
    }
    elements.organizationAgentPassword.focus();
    return;
  }
  elements.organizationAgentAdd.disabled = true;
  try {
    const base = `/api/v1/orbit/organizations/${encodeURIComponent(organization.id)}/agents/${encodeURIComponent(selectedAgent.id)}`;
    let confirmationToken = "";
    if (intent === "remove") {
      const confirmed = await requestJson(`${base}/confirmation`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": state.csrfToken },
        body: JSON.stringify({ intent, password: elements.organizationAgentPassword.value }),
      });
      confirmationToken = confirmed.confirmation_token;
    }
    await requestJson(base, {
      method: intent === "assign" ? "PUT" : "DELETE",
      headers: {
        "X-CSRF-Token": state.csrfToken,
        ...(confirmationToken ? { "X-Human-Confirmation": confirmationToken } : {}),
      },
    });
    elements.organizationAgentPassword.value = "";
    await loadDashboard();
    state.managedOrganization = (state.dashboard?.organizations || []).find(
      (item) => String(item.id) === String(organization.id),
    ) || organization;
    renderOrganizationAgents(state.managedOrganization);
    elements.organizationManageResult.textContent = intent === "assign"
      ? "Agent 已加入组织；只有明确发到“组织协作”的新内容才会共享。"
      : "Agent 已移出组织；组织派生的查看权限已撤销。";
    elements.organizationManageResult.className = "form-status success";
  } catch (error) {
    const conflicts = {
      agent_already_assigned_to_organization: "这个 Agent 已属于其他组织，不能自动迁移。",
      human_reauthentication_failed: "密码不正确，或当前浏览器尚未完成双重验证登录。",
      organization_agent_not_found: "只能管理你本人拥有且仍处于活动状态的 Agent。",
      organization_management_forbidden: "你当前是只读审计角色，不能把 Agent 加入或移出组织。请联系组织管理员调整角色。",
    };
    elements.organizationManageResult.textContent = conflicts[error.code] || error.message;
    elements.organizationManageResult.className = "form-status error";
  } finally {
    elements.organizationAgentPassword.value = "";
    renderOrganizationAgents(state.managedOrganization || organization);
  }
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
  elements.organizationAgentPassword.value = "";
  elements.organizationAgentSelect.replaceChildren();
  elements.organizationInviteUsername.value = "";
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
  elements.organizationInviteRole.replaceChildren();
  elements.organizationLeave.disabled = false;
  elements.organizationLeave.textContent = "退出组织";
  state.managedOrganization = null;
  state.organizationDomainProofs.clear();
  if (elements.organizationManageDialog.open) {
    elements.organizationManageDialog.close();
  }
}

function configureOrganizationInvitationRoles(actorRole) {
  elements.organizationInviteRole.replaceChildren();
  const roles = actorRole === "owner" ? ["member", "auditor", "admin"] : ["member", "auditor"];
  roles.forEach((role) => {
    const option = document.createElement("option");
    option.value = role;
    option.textContent = statusLabel(role);
    elements.organizationInviteRole.append(option);
  });
}

function configureOrganizationLeave(members) {
  const organization = state.managedOrganization;
  const ownerCount = members.filter((member) => member.role === "owner").length;
  const isLastOwner = organization?.membership_role === "owner" && ownerCount <= 1;
  elements.organizationLeave.disabled = isLastOwner;
  elements.organizationLeave.textContent = isLastOwner ? "请先转交 Owner 角色" : "退出组织";
  elements.organizationLeave.title = isLastOwner
    ? "最后一名 Owner 不能直接退出；请先把另一名成员提升为 Owner"
    : "退出后只撤销组织派生权限，个人和直接授权保持不变";
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
    const card = document.createElement("article");
    card.className = "organization-member-card";
    const heading = document.createElement("div");
    heading.className = "organization-member-heading";
    const identity = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = safeText(member.human_display_name, member.human_username);
    const identityDetail = document.createElement("span");
    identityDetail.textContent = `@${safeText(member.human_username)}`;
    identity.append(name, identityDetail);
    const actions = document.createElement("div");
    actions.className = "governance-row-actions";
    actions.append(chip(member.role, "role"));
    heading.append(identity, actions);
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
    const agentSection = document.createElement("div");
    agentSection.className = "organization-member-agents";
    const memberAgents = Array.isArray(member.agents) ? member.agents : [];
    const agentCount = document.createElement("span");
    agentCount.className = "organization-member-agent-count";
    agentCount.textContent = memberAgents.length ? `${memberAgents.length} 个 Agent` : "尚未设置可参与的 Agent";
    agentSection.append(agentCount);
    memberAgents.forEach((memberAgent) => {
      const item = document.createElement("div");
      item.className = "organization-member-agent";
      const agentIdentity = document.createElement("div");
      const agentName = document.createElement("strong");
      agentName.textContent = safeText(memberAgent.handle, memberAgent.display_name);
      const dashboardAgent = (state.dashboard?.agents || []).find(
        (agent) => String(agent.id) === String(memberAgent.agent_id),
      );
      const agentDetail = document.createElement("span");
      const sourceLabel = memberAgent.participation_source === "default" ? "默认参与" : "已加入组织";
      agentDetail.textContent = dashboardAgent
        ? `${sourceLabel} · ${statusLabel(dashboardAgent.connection_state)} · ${safeText(memberAgent.display_name)}`
        : `${sourceLabel} · ${safeText(memberAgent.display_name)}`;
      agentIdentity.append(agentName, agentDetail);
      item.append(agentIdentity);
      if (
        isSelf
        && memberAgent.participation_source !== "default"
        && dashboardAgent?.role === "owner"
        && ["owner", "admin", "member"].includes(actorRole)
      ) {
        const removeAgent = document.createElement("button");
        removeAgent.type = "button";
        removeAgent.className = "quiet-button danger";
        removeAgent.textContent = "移出组织";
        removeAgent.addEventListener("click", () => changeOwnedOrganizationAgent(dashboardAgent, "remove"));
        item.append(removeAgent);
      }
      agentSection.append(item);
    });
    card.append(heading, agentSection);
    elements.organizationMemberList.append(card);
  });
  const groupedAgentIds = new Set(
    members.flatMap((member) => (member.agents || []).map((agent) => String(agent.agent_id))),
  );
  const ungroupedAgents = (state.dashboard?.agents || []).filter(
    (agent) => String(agent.organization?.id || "") === String(organization?.id)
      && !groupedAgentIds.has(String(agent.id)),
  );
  if (ungroupedAgents.length) {
    const ungroupedCard = document.createElement("article");
    ungroupedCard.className = "organization-member-card organization-ungrouped-agents";
    const title = document.createElement("strong");
    title.textContent = "待确认归属的 Agent";
    const note = document.createElement("span");
    note.textContent = "这些 Agent 已在组织中，但还没有关联到具体成员。";
    ungroupedCard.append(title, note);
    ungroupedAgents.forEach((agent) => {
      const item = document.createElement("div");
      item.className = "organization-member-agent";
      const identity = document.createElement("div");
      const name = document.createElement("strong");
      name.textContent = agentDisplayName(agent);
      const detail = document.createElement("span");
      detail.textContent = `${statusLabel(agent.connection_state)} · ${safeText(agent.display_name)}`;
      identity.append(name, detail);
      item.append(identity);
      ungroupedCard.append(item);
    });
    elements.organizationMemberList.append(ungroupedCard);
  }
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
      invitation.username || invitation.email || "目标用户",
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
    elements.organizationManageResult.textContent = "单位统一登录已停用；已有成员账户和操作记录会继续保留。";
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
    elements.organizationOidcList.append(emptyState("尚未开通单位统一登录。"));
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
    elements.organizationManageResult.textContent = "请完整填写单位登录配置；客户端密钥至少 12 个字符。";
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
    elements.organizationManageResult.textContent = "单位统一登录已开通；客户端密钥不会再次显示。";
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
  renderOrganizationAgents(organization);
  elements.organizationInviteSection.hidden = !isManager;
  elements.organizationInviteUsername.disabled = !isManager;
  elements.organizationInviteRole.disabled = !isManager;
  configureOrganizationInvitationRoles(organization.membership_role);
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
  const memberItems = Array.isArray(members.items) ? members.items : [];
  renderOrganizationMembers(memberItems);
  configureOrganizationLeave(memberItems);
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
  elements.organizationManageTitle.textContent = safeText(organization.name, organization.slug);
  elements.organizationManageSummary.textContent = `${organization.slug} · ${organizationRoleExperience(organization.membership_role).capability}`;
  elements.organizationManageResult.textContent = "成员管理和组织设置会根据你的权限自动显示。";
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
          username: elements.organizationInviteUsername.value.trim().toLowerCase(),
          role: elements.organizationInviteRole.value,
        }),
      },
    );
    elements.organizationInviteUsername.value = "";
    elements.organizationManageResult.textContent = "站内邀请已发出；对方登录星云驿后即可接受。";
    elements.organizationManageResult.className = "form-status success";
    await loadOrganizationManagement();
  } catch (error) {
    const messages = {
      organization_invitee_not_found: "没有找到这个 Human 用户名。请核对对方在星云驿中的用户名后再试。",
      organization_already_member: "这位 Human 已经是组织成员。",
      organization_invitation_already_pending: "已经向这位 Human 发出过待接受邀请，无需重复邀请。",
    };
    elements.organizationManageResult.textContent = messages[error.code] || error.message;
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

function closeOrganizationInvitationDialog() {
  state.pendingOrganizationInvitation = "";
  elements.organizationInvitationName.textContent = "—";
  elements.organizationInvitationSlug.textContent = "—";
  elements.organizationInvitationRole.textContent = "—";
  elements.organizationInvitationExpiry.textContent = "—";
  elements.organizationInvitationCapability.textContent = "—";
  elements.organizationInvitationVisibility.textContent = "—";
  elements.organizationInvitationActions.textContent = "—";
  elements.organizationInvitationResult.textContent = "";
  if (elements.organizationInvitationDialog.open) {
    elements.organizationInvitationDialog.close();
  }
}

async function acceptOrganizationInvitation(event) {
  event.preventDefault();
  const token = state.pendingOrganizationInvitation;
  if (!token || !state.csrfToken) {
    return;
  }
  elements.organizationInvitationSubmit.disabled = true;
  try {
    await requestJson("/api/v1/orbit/organization-invitations/accept", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": state.csrfToken },
      body: JSON.stringify({ token }),
    });
    state.pendingOrganizationInvitation = "";
    if (elements.organizationInvitationDialog.open) {
      elements.organizationInvitationDialog.close();
    }
    await loadDashboard();
    activateRoute("settings", "organizations", { updateHistory: true });
    setConnection("组织邀请已接受", "success");
  } catch (error) {
    elements.organizationInvitationResult.textContent = error.message;
    elements.organizationInvitationResult.className = "form-status error";
  } finally {
    elements.organizationInvitationSubmit.disabled = false;
  }
}

async function maybePreviewOrganizationInvitation() {
  const token = state.pendingOrganizationInvitation;
  if (!token || !state.csrfToken) {
    return;
  }
  try {
    const preview = await requestJson("/api/v1/orbit/organization-invitations/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    });
    const experience = organizationRoleExperience(preview.role);
    elements.organizationInvitationName.textContent = safeText(preview.organization_name);
    elements.organizationInvitationSlug.textContent = safeText(preview.organization_slug);
    elements.organizationInvitationRole.textContent = statusLabel(preview.role);
    elements.organizationInvitationExpiry.textContent = `邀请有效至 ${dateText(preview.expires_at)}`;
    elements.organizationInvitationCapability.textContent = experience.capability;
    elements.organizationInvitationVisibility.textContent = experience.visibility;
    elements.organizationInvitationActions.textContent = experience.actions;
    elements.organizationInvitationResult.textContent = "请确认后再加入；关闭窗口不会接受邀请。";
    elements.organizationInvitationResult.className = "form-status";
    elements.organizationInvitationDialog.showModal();
    elements.organizationInvitationSubmit.focus();
  } catch (error) {
    state.pendingOrganizationInvitation = "";
    setConnection("组织邀请无法预览", "error");
    setFormStatus(error.message, "error");
  }
}

function renderAgents(agents) {
  renderAgentOverview(agents);
  renderAgentBrowser(agents);
  if (state.selectedAgentId) {
    const agent = agents.find((item) => String(item.id) === state.selectedAgentId);
    if (agent) {
      renderAgentDetail(agent);
      void loadAgentRelatedThreads(agent);
    } else {
      renderMissingAgent();
    }
  } else {
    renderAgentOverviewState();
  }
}

function agentConnectionCopy(agent) {
  const copies = {
    connected: `${safeText(agent.current_connector_name, agent.current_connector_type || "当前连接")} 正常连接，最近报到 ${dateText(agent.current_connector_last_heartbeat_at)}`,
    awaiting_agent: "你已完成授权，正在等待 Agent 完成设置并首次上线",
    disconnected: "没有当前有效连接；Agent 身份和历史仍保留",
    offline: `曾经连接，但最近报到已超时（${dateText(agent.current_connector_last_heartbeat_at)}）`,
    connection_error: `检测到明确连接异常${agent.current_connector_error_code ? `：${safeText(agent.current_connector_error_code)}` : ""}`,
  };
  return copies[agent.connection_state] || "连接证据不足";
}

function agentMatchesQuery(agent) {
  if (!state.agentQuery) {
    return true;
  }
  const searchable = [
    agent.handle,
    agent.display_name,
    agent.address,
    agent.current_connector_type,
    agent.organization?.name,
    ...(agent.capabilities || []),
  ].map((value) => safeText(value, "").toLocaleLowerCase("zh-CN"));
  return searchable.some((value) => value.includes(state.agentQuery.toLocaleLowerCase("zh-CN")));
}

function groupedAgents(agents) {
  const personal = [];
  const organizations = new Map();
  agents.forEach((agent) => {
    if (agent.organization) {
      const key = String(agent.organization.id);
      if (!organizations.has(key)) {
        organizations.set(key, { organization: agent.organization, agents: [] });
      }
      organizations.get(key).agents.push(agent);
    } else {
      personal.push(agent);
    }
  });
  return { personal, organizations: Array.from(organizations.values()) };
}

function renderAgentOverview(agents) {
  const counts = {
    connected: 0,
    awaiting_agent: 0,
    offline: 0,
    connection_error: 0,
  };
  agents.forEach((agent) => {
    if (Object.hasOwn(counts, agent.connection_state)) {
      counts[agent.connection_state] += 1;
    }
  });
  elements.agentStatAll.textContent = String(agents.length);
  elements.agentStatConnected.textContent = String(counts.connected);
  elements.agentStatAwaiting.textContent = String(counts.awaiting_agent);
  elements.agentStatOffline.textContent = String(counts.offline);
  elements.agentStatError.textContent = String(counts.connection_error);
  elements.agentOverviewGroups.replaceChildren();
  if (!agents.length) {
    elements.agentOverviewGroups.append(emptyState("还没有可查看的 Agent。连接新的 Agent 后会在这里出现。"));
    return;
  }
  const groups = groupedAgents(agents);
  const values = [["我的 Agent", groups.personal.length, "个人所有权和直接授权不会因加入组织而公开"]];
  groups.organizations.forEach((group) => {
    values.push([
      safeText(group.organization.name),
      group.agents.length,
      `你的组织角色：${statusLabel(group.organization.membership_role)}`,
    ]);
  });
  values.forEach(([name, count, copy]) => {
    const card = document.createElement("article");
    const label = document.createElement("span");
    label.textContent = name;
    const number = document.createElement("strong");
    number.textContent = `${count} 个`;
    const description = document.createElement("p");
    description.textContent = copy;
    card.append(label, number, description);
    elements.agentOverviewGroups.append(card);
  });
}

function agentBrowserButton(agent) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "agent-browser-item";
  button.classList.toggle("active", String(agent.id) === state.selectedAgentId);
  if (String(agent.id) === state.selectedAgentId) {
    button.setAttribute("aria-current", "true");
  }
  const identity = document.createElement("span");
  identity.className = "agent-browser-identity";
  const avatar = agentAvatar(agent, "agent-mini-avatar");
  const names = document.createElement("span");
  const name = document.createElement("strong");
  name.textContent = agentDisplayName(agent);
  const display = document.createElement("small");
  display.textContent = `${safeText(agent.display_name)} · ${agent.current_connector_type ? agentTypeLabel({ agent_type: agent.current_connector_type }) : "类型未提供"}`;
  names.append(name, display);
  identity.append(avatar, names);
  const status = chip(agent.connection_state);
  button.append(identity, status);
  button.addEventListener("click", () => selectAgent(String(agent.id)));
  return button;
}

function renderAgentBrowser(agents) {
  const visible = agents.filter(agentMatchesQuery);
  elements.agentBrowserCount.textContent = `${visible.length} 个`;
  elements.agentBrowserList.replaceChildren();
  if (!visible.length) {
    elements.agentBrowserList.append(emptyState(
      state.agentQuery ? "没有找到符合条件且你有权查看的 Agent。" : "当前没有可查看的 Agent。",
    ));
    return;
  }
  const groups = groupedAgents(visible);
  const appendGroup = (title, values) => {
    if (!values.length) return;
    const section = document.createElement("section");
    section.className = "agent-browser-group";
    const heading = document.createElement("h3");
    heading.textContent = `${title} · ${values.length}`;
    section.append(heading);
    values.forEach((agent) => section.append(agentBrowserButton(agent)));
    elements.agentBrowserList.append(section);
  };
  appendGroup("我的 Agent", groups.personal);
  groups.organizations.forEach((group) => {
    appendGroup(safeText(group.organization.name), group.agents);
  });
}

function renderAgentOverviewState() {
  state.selectedAgent = null;
  elements.agentOverview.hidden = false;
  elements.agentDetail.hidden = true;
  elements.agentDetailMissing.hidden = true;
  updateAgentWorkspaceMode();
  document.title = "星云驿 · 云驿";
}

function detailFact(label, value, copy = "") {
  const card = document.createElement("article");
  const name = document.createElement("span");
  name.textContent = label;
  const detail = document.createElement("strong");
  detail.textContent = safeText(value);
  card.append(name, detail);
  if (copy) {
    const description = document.createElement("p");
    description.textContent = copy;
    card.append(description);
  }
  return card;
}

function renderCurrentAgentConnection(agent) {
  elements.agentCurrentConnection.replaceChildren();
  const intro = document.createElement("div");
  intro.className = `agent-connection-banner ${agent.connection_state}`;
  const heading = document.createElement("strong");
  heading.textContent = statusLabel(agent.connection_state);
  const copy = document.createElement("p");
  copy.textContent = agentConnectionCopy(agent);
  intro.append(heading, copy);
  elements.agentCurrentConnection.append(intro);
  if (agent.connection_state === "disconnected") {
    return;
  }
  const facts = document.createElement("div");
  facts.className = "agent-detail-summary";
  [
    ["Agent 类型", agent.current_connector_type || "未提供"],
    ["当前连接", agent.current_connector_name || "名称未提供"],
    ["设备", agent.current_connector_device || "设备未提供"],
    ["最近报到", dateText(agent.current_connector_last_heartbeat_at)],
    ["健康证据", statusLabel(agent.current_connector_health || "unknown")],
  ].forEach(([label, value]) => facts.append(detailFact(label, value)));
  const technical = document.createElement("details");
  technical.className = "agent-technical-details";
  const summary = document.createElement("summary");
  summary.textContent = "查看连接详情";
  const version = document.createElement("p");
  version.textContent = `连接版本：${safeText(agent.current_connector_version, "未提供")}`;
  technical.append(summary, version);
  elements.agentCurrentConnection.append(facts, technical);
}

function renderAgentConnectionHistory(agent) {
  elements.agentConnectionHistory.replaceChildren();
  if (agent.role !== "owner") {
    elements.agentConnectionHistory.append(emptyState("连接历史属于 Agent 所有者的审计信息；当前权限只提供连接状态。"));
    return;
  }
  const history = state.connectors.filter(
    (connector) => String(connector.agent?.id) === String(agent.id)
      && !(connector.is_current && connector.status === "active"),
  );
  if (!history.length) {
    elements.agentConnectionHistory.append(emptyState("还没有过去的连接记录。"));
    return;
  }
  history.forEach((connector) => elements.agentConnectionHistory.append(connectorCard(connector, true)));
}

function renderAgentAccess(agent) {
  elements.agentDetailAccess.replaceChildren();
  elements.agentDetailAccess.append(
    detailFact("当前权限", statusLabel(agent.role), "可执行的操作以你的实际权限为准。"),
    detailFact("权限来源", agent.access_source === "organization" ? "组织派生" : "直接关系"),
    detailFact("所属组织", agent.organization?.name || "个人范围"),
    detailFact(
      "组织角色",
      agent.organization?.membership_role ? statusLabel(agent.organization.membership_role) : "不适用",
      "组织成员关系不会自动变成 Agent 所有权。",
    ),
  );
}

function renderAgentCapabilities(agent) {
  elements.agentDetailCapabilities.replaceChildren();
  const values = Array.isArray(agent.capabilities) ? agent.capabilities : [];
  if (!values.length) {
    const empty = document.createElement("span");
    empty.textContent = "Agent 尚未声明能力";
    elements.agentDetailCapabilities.append(empty);
    return;
  }
  values.forEach((capability) => {
    const value = document.createElement("span");
    value.textContent = safeText(capability);
    elements.agentDetailCapabilities.append(value);
  });
}

function renderAgentTab() {
  elements.agentDetailTabs.forEach((button) => {
    const active = button.dataset.agentTab === state.agentTab;
    button.classList.toggle("active", active);
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  elements.agentDetailPanels.forEach((panel) => {
    panel.hidden = panel.dataset.agentPanel !== state.agentTab;
  });
}

function renderAgentDetail(agent) {
  state.selectedAgent = agent;
  elements.agentOverview.hidden = true;
  elements.agentDetailMissing.hidden = true;
  elements.agentDetail.hidden = false;
  elements.agentDetailName.textContent = agentDisplayName(agent);
  elements.agentDetailSubtitle.textContent = agent.handle
    ? `${safeText(agent.display_name)} · ${agent.organization?.name || "个人范围"}`
    : `${safeText(agent.display_name)} · 尚未设置短名称`;
  elements.agentDetailAvatar.textContent = agentDisplayName(agent).slice(0, 1).toUpperCase();
  elements.agentDetailAvatar.style.setProperty("--agent-hue", String(agentHue(agent)));
  elements.agentDetailStatus.className = `data-chip ${agent.connection_state}`;
  elements.agentDetailStatus.textContent = statusLabel(agent.connection_state);
  elements.agentDetailSummary.replaceChildren(
    detailFact("常用名称", agentDisplayName(agent)),
    detailFact("显示名称", agent.display_name),
    detailFact(
      "别人通过我的用户名联系时",
      agent.is_default ? "由这个 Agent 接收" : "由其他默认 Agent 接收",
    ),
    detailFact("最近活动", dateText(agent.last_seen_at)),
    detailFact("待 Agent 读取", agent.unread_count, "表示消息还未被 Agent 读取。"),
    detailFact("进行中任务", agent.pending_task_count),
  );
  const identity = document.createElement("details");
  identity.className = "agent-technical-details";
  const identitySummary = document.createElement("summary");
  identitySummary.textContent = "查看底层身份";
  const address = document.createElement("p");
  address.textContent = safeText(agent.address);
  identity.append(identitySummary, address);
  elements.agentDetailSummary.append(identity);
  renderCurrentAgentConnection(agent);
  renderAgentCapabilities(agent);
  renderAgentAccess(agent);
  renderAgentConnectionHistory(agent);
  const owner = agent.role === "owner";
  elements.agentOwnerActions.hidden = !owner;
  elements.agentReadonlyActions.hidden = owner;
  elements.agentRename.hidden = !owner;
  elements.agentSetDefault.hidden = !owner;
  elements.agentSetDefault.disabled = Boolean(agent.is_default);
  elements.agentSetDefault.textContent = agent.is_default ? "默认 Agent" : "设为默认 Agent";
  const currentOwnedConnector = state.connectors.find(
    (connector) => String(connector.agent?.id) === String(agent.id)
      && connector.is_current && connector.status === "active",
  );
  elements.agentDisconnect.hidden = !currentOwnedConnector;
  elements.agentRename.textContent = agent.handle ? "修改短名称" : "设置短名称";
  const returnThread = new URLSearchParams(window.location.search).get("returnThread");
  elements.agentReturnThread.hidden = !returnThread;
  renderAgentTab();
  updateAgentWorkspaceMode();
  document.title = `星云驿 · ${agentDisplayName(agent)}`;
}

function renderMissingAgent() {
  state.selectedAgent = null;
  elements.agentOverview.hidden = true;
  elements.agentDetail.hidden = true;
  elements.agentDetailMissing.hidden = false;
  updateAgentWorkspaceMode();
}

async function loadAgentRelatedThreads(agent) {
  state.agentRelatedThreads = [];
  elements.agentRelatedThreads.replaceChildren(emptyState("正在读取相关对话…"));
  try {
    const threads = await requestJson(
      `/api/v1/orbit/threads?limit=200&agent_id=${encodeURIComponent(agent.id)}`,
    );
    if (!state.selectedAgent || String(state.selectedAgent.id) !== String(agent.id)) {
      return;
    }
    state.agentRelatedThreads = Array.isArray(threads) ? threads : [];
    elements.agentRelatedThreads.replaceChildren();
    if (!state.agentRelatedThreads.length) {
      elements.agentRelatedThreads.append(emptyState("这个 Agent 还没有你有权查看的相关对话。"));
      return;
    }
    state.agentRelatedThreads.forEach((thread) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "agent-related-thread";
      const topic = document.createElement("strong");
      topic.textContent = safeText(thread.topic, "无主题对话");
      const meta = document.createElement("span");
      meta.textContent = `${thread.message_count} 条消息 · ${dateText(thread.latest_activity_at)}`;
      button.append(topic, meta);
      button.addEventListener("click", () => openRelatedThread(String(thread.thread_id)));
      elements.agentRelatedThreads.append(button);
    });
  } catch (_error) {
    elements.agentRelatedThreads.replaceChildren(emptyState("相关对话暂时无法读取，请稍后刷新。"));
  }
}

function openRelatedThread(threadId) {
  state.selectedThreadId = threadId;
  state.threadQuery = "";
  state.threadFilter = "all";
  state.threadOrganization = "";
  const url = new URL(window.location.href);
  ["agent", "agentTab", "agentQuery", "returnThread"].forEach((name) => url.searchParams.delete(name));
  url.searchParams.set("module", "orbit");
  url.searchParams.set("view", "communications");
  url.searchParams.set("thread", threadId);
  url.searchParams.delete("q");
  url.searchParams.delete("filter");
  url.searchParams.delete("organization");
  history.pushState({ module: "orbit", section: "communications", thread: threadId }, "", `${url.pathname}${url.search}`);
  activateRoute("orbit", "communications", { updateHistory: false, focusContent: true });
  renderThreadList();
  void loadThreadDetail(threadId);
}

function selectAgent(agentId, { updateHistory = true } = {}) {
  state.selectedAgentId = String(agentId);
  state.agentTab = "summary";
  const agent = (state.dashboard?.agents || []).find(
    (item) => String(item.id) === state.selectedAgentId,
  );
  renderAgentBrowser(state.dashboard?.agents || []);
  if (updateHistory) {
    history.pushState({ module: "relay", section: "agents", agent: agentId }, "", agentRouteUrl());
  }
  if (agent) {
    renderAgentDetail(agent);
    void loadAgentRelatedThreads(agent);
    if (isMobileWorkspace()) {
      elements.agentMobileBack.scrollIntoView({ block: "start" });
      elements.agentMobileBack.focus({ preventScroll: true });
    } else {
      elements.agentDetailName.focus({ preventScroll: true });
    }
  } else {
    renderMissingAgent();
  }
}

function clearAgentSelection({ updateHistory = true } = {}) {
  state.selectedAgentId = "";
  state.selectedAgent = null;
  state.agentTab = "summary";
  renderAgentBrowser(state.dashboard?.agents || []);
  renderAgentOverviewState();
  if (updateHistory) {
    history.pushState({ module: "relay", section: "agents" }, "", agentRouteUrl());
  }
  resetMobileLayerScroll();
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
  const handleProblem = agentHandleProblem(handle);
  if (!agentId || handleProblem) {
    elements.handleResult.textContent = handleProblem || "没有找到要修改的 Agent，请关闭后重试。";
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

async function setSelectedAgentAsDefault() {
  const agent = state.selectedAgent;
  if (!agent || agent.role !== "owner" || agent.is_default) return;
  elements.agentSetDefault.disabled = true;
  elements.agentSetDefault.textContent = "正在设置…";
  try {
    await requestJson(`/api/v1/orbit/agents/${encodeURIComponent(agent.id)}/default`, {
      method: "PUT",
      headers: { "X-CSRF-Token": state.csrfToken },
    });
    await loadDashboard();
    setConnection(`${agentDisplayName(agent)} 已设为默认 Agent`, "success");
  } catch (error) {
    elements.agentSetDefault.disabled = false;
    elements.agentSetDefault.textContent = "设为默认 Agent";
    setConnection(error.message, "error");
  }
}

function openRevokeDialog(connector) {
  elements.revokeConnectorId.value = safeText(connector.connector_id, "");
  const agentLabel = connector.agent?.handle || connector.agent?.display_name || connector.agent?.address;
  elements.revokeSummary.textContent = `将断开 ${safeText(agentLabel, "这个 Agent")} 当前使用的 ${safeText(connector.display_name)} 连接。`;
  elements.revokeResult.textContent = "请重新输入当前密码（或旧版集成凭证）；验证后输入内容会立即清除。";
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
  technicalSummary.textContent = "查看连接详情";
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
  workbuddy: { name: "WorkBuddy", code: "AP-WORKBUDDY-V1", defaultHandle: "workbuddy" },
  doubao_work: { name: "豆包工作", code: "AP-DOUBAO-WORK-V1", defaultHandle: "doubao", connectionMode: "local_bootstrap" },
  openclaw: { name: "OpenClaw", code: "AP-OPENCLAW-V1", defaultHandle: "openclaw" },
  hermes: { name: "Hermes", code: "AP-HERMES-V1", defaultHandle: "hermes" },
  codex: { name: "Codex", code: "AP-CODEX-V1", defaultHandle: "codex" },
  manus: { name: "Manus", code: "AP-MANUS-V1", defaultHandle: "manus", connectionMode: "local_bootstrap" },
});

function agentHandleProblem(value) {
  const handle = value.trim().toLowerCase();
  if (!handle) return "";
  if (handle.length > 32) return `短名称最多 32 位；目前有 ${handle.length} 位。`;
  if (handle.startsWith("-") || handle.endsWith("-") || handle.includes("--")) {
    return "连字符不能放在开头或结尾，也不能连续使用。";
  }
  if (!/^[\p{L}\p{N}-]+$/u.test(handle)) {
    return "短名称只能使用中文、英文字母、数字和连字符“-”，不能使用空格、下划线或其他符号。";
  }
  if (RESERVED_AGENT_HANDLES.has(handle)) {
    return `“${handle}”是系统保留名称，请换一个更具体的名称。`;
  }
  return "";
}

function defaultPairingHandle(connectorType) {
  const base = PAIRING_HOSTS[connectorType]?.defaultHandle || "agent";
  const used = new Set((state.dashboard?.agents || [])
    .map((agent) => safeText(agent.handle, "").toLowerCase())
    .filter(Boolean));
  if (!used.has(base)) return base;
  for (let suffix = 2; suffix < 1000; suffix += 1) {
    const candidate = `${base}-${suffix}`;
    if (!used.has(candidate)) return candidate;
  }
  return base;
}

function setSuggestedPairingHandle(connectorType) {
  const current = elements.pairingHandle.value.trim().toLowerCase();
  if (current && current !== state.pairingSuggestedHandle) return;
  const suggestion = defaultPairingHandle(connectorType);
  state.pairingSuggestedHandle = suggestion;
  elements.pairingHandle.value = suggestion;
  updatePairingHandleHelp();
}

function updatePairingHandleHelp() {
  const handle = elements.pairingHandle.value.trim().toLowerCase();
  const problem = agentHandleProblem(handle);
  elements.pairingHandleHelp.textContent = problem
    || (handle
      ? `连接后可用“${handle}”找到这个 Agent，以后也可以修改。`
      : "系统会按 Agent 平台自动填写；也可以改为 1–32 个中文、英文字母或数字。");
  elements.pairingHandleHelp.classList.toggle("error", Boolean(problem));
}

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
  const connectionMode = selected.connectionMode || state.authConfig?.host_connection_modes?.[host];
  const instructions = connectionMode === "remote_mcp_oauth"
    ? `请读取这个官方接入页，使用 ${selected.name} 内置的 Custom MCP 连接和星轨网页授权直接完成接入。不要安装 AgentPost 本机程序，也不要让我输入服务器地址、命令、密钥或其他技术参数；如果当前 ${selected.name} 不支持安全网页授权，必须明确停止，不能改用长期密钥或假装已连接。连接后回到本对话继续。`
    : host === "manus"
      ? `请先在 Manus 中创建或选择一个专用本地文件夹，再读取这个官方接入页并完成安全配对。接入程序会在该文件夹生成 AGENTS.md、xingyunyi 和校验文件，密钥仍只保存在系统钥匙串。文件生成后必须新建 Manus 任务，提交前选择这个文件夹；不要复用旧任务。先运行 ./xingyunyi status，确认身份一致且连接正常后再继续；不要改用 Custom MCP 或 Remote MCP。`
    : host === "doubao_work"
      ? `请读取这个官方接入页并完成本机安全配对。接入程序会准备好 ${selected.name} STDIO 连接器所需的唯一启动项；不要让我自行填写服务器、参数、环境变量或密钥。若 ${selected.name} 不允许自动写入连接器，我只需粘贴这一项并保存一次。确认星云驿工具已在真实任务中出现后，再回到本对话继续。`
      : "请读取这个官方接入页并直接完成安装和授权。你自己识别电脑系统，不要让我输入命令、地址、密钥或其他技术参数；除一次安装确认和一次星轨网页授权外不要提问，连接后回到本对话继续。";
  return [
    target
      ? `请把当前 ${selected.name} 重新连接到我已有的 Agent“${targetLabel}”，保留原身份和历史。`
      : `请把当前 ${selected.name} 作为新的独立 Agent 连接到我的星云驿。`,
    `接入码：${selected.code} https://agentpost.me/connect/${host}${targetQuery}`,
    instructions,
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
    state.pairingSuggestedHandle = "";
    updatePairingHandleHelp();
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
    elements.pairingHandle.value = safeText(requestedAgent.handle, "");
    state.pairingSuggestedHandle = elements.pairingHandle.value;
    updatePairingHandleHelp();
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
    setSuggestedPairingHandle(safeText(pairing.connector_type, ""));
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
  const handleProblem = agentHandleProblem(payload.handle || "");
  if (handleProblem) return handleProblem;
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
  const payload = pairingPayload(decision);
  const payloadProblem = pairingPayloadProblem(decision, payload);
  if (!state.csrfToken || !pairingId.startsWith("pair_") || !userCode || !validReauthenticationCandidate(humanKey)) {
    elements.pairingResult.textContent = "请填写有效的配对信息、一次性配对码和当前密码（或旧版集成凭证）。";
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
    if (agentHandleProblem(payload.handle || "")) {
      elements.pairingHandle.focus();
    } else {
      elements.pairingLocalId.focus();
    }
    return;
  }
  elements.pairingSubmit.disabled = true;
  elements.pairingDeny.disabled = true;
  elements.pairingResult.textContent = "正在验证配对码和你的身份…";
  elements.pairingResult.className = "form-status";
  try {
    let confirmation;
    try {
      const proof = reauthentication(humanKey, "", {
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
    const oauthRequest = new URLSearchParams(window.location.search).get("oauth_request") || "";
    closePairingDialog();
    if (oauthRequest) {
      const completion = new URL("/api/v1/orbit/oauth/authorize/complete", window.location.origin);
      completion.searchParams.set("authorization_request", oauthRequest);
      const completed = await requestJson(completion.toString(), {
        method: "POST",
        headers: { "X-CSRF-Token": state.csrfToken },
      });
      window.location.assign(completed.redirect_to);
      return;
    }
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
    elements.revokeResult.textContent = "请重新输入当前密码（或旧版集成凭证）。";
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
  elements.approvalResult.textContent = "请重新输入当前密码（或旧版集成凭证）；验证后输入内容会立即清除。";
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

function agentOwnerLabel(agent, { currentAsMe = false } = {}) {
  if (currentAsMe && agent?.owned_by_current_human) {
    return "我";
  }
  return safeText(agent?.owner_username, agent?.owner_display_name || "归属人待确认");
}

function agentConversationLabel(agent, options = {}) {
  return `${agentOwnerLabel(agent, options)} · ${agentDisplayName(agent)}`;
}

function agentTypeLabel(agent) {
  const labels = {
    codex: "Codex",
    workbuddy: "WorkBuddy",
    doubao_work: "豆包工作",
    openclaw: "OpenClaw",
    manus: "Manus",
    hermes: "Hermes",
  };
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
  const organizationsWithThreads = new Set(
    state.threads
      .filter((thread) => thread.channel_scope === "organization")
      .map((thread) => String(thread.organization_id || (thread.organizations || [])[0]?.id || ""))
      .filter(Boolean),
  );
  const organizationChannels = state.threadFilter === "archived" ? [] : (state.dashboard?.organizations || [])
    .filter((organization) => !organizationsWithThreads.has(String(organization.id)))
    .map((organization) => ({
      thread_id: `organization:${organization.id}`,
      topic: `${safeText(organization.name, organization.slug)} 群聊`,
      latest_activity_at: null,
      human_view_state: "viewed",
      latest_sender: null,
      latest_recipient: null,
      latest_content_redacted: false,
      latest_message_summary: "群聊已建立。成员未指定 Agent 时，默认 Agent 会自动参与。",
      message_count: 0,
      attachment_count: 0,
      exception_count: 0,
      conversation_state: "updated",
      channel_scope: "organization",
      organization_id: organization.id,
      organization_name: safeText(organization.name, organization.slug),
      organizations: [organization],
      virtual_organization_channel: true,
    }));
  return [...organizationChannels, ...state.threads].filter((thread) => {
    if (thread.virtual_organization_channel && state.threadQuery) {
      const organization = (thread.organizations || [])[0];
      const searchable = `${thread.topic} ${organization?.slug || ""}`.toLocaleLowerCase();
      if (!searchable.includes(state.threadQuery.toLocaleLowerCase())) {
        return false;
      }
    }
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

function conversationStateLabel(value) {
  const labels = {
    needs_attention: "需要关注",
    in_progress: "正在协作",
    completed: "已完成",
    waiting_for_me: "等待我回复",
    waiting_for_other: "等待对方回复",
    updated: "有新进展",
  };
  return labels[value] || "对话进行中";
}

function renderThreadParentSummary() {
  const total = visibleThreadSummaries().filter(
    (thread) => !thread.virtual_organization_channel,
  ).length;
  const unread = visibleThreadSummaries().filter(
    (thread) => thread.human_view_state === "unread",
  ).length;
  const stateLabel = state.threadBrowserExpanded ? "已展开" : "已折叠";
  const scopeLabel = state.threadFilter === "archived" ? "已归档" : stateLabel;
  elements.threadParentSummary.textContent = `${scopeLabel} · ${total} 个完整对话`;
  elements.threadUnreadCount.textContent = String(unread);
  elements.threadUnreadCount.hidden = unread === 0;
}

function threadOrganization(thread) {
  if (thread.channel_scope !== "organization") {
    return null;
  }
  return (thread.organizations || []).find(
    (organization) => String(organization.id) === String(thread.organization_id),
  ) || (thread.organizations || [])[0] || (thread.organization_id ? {
    id: thread.organization_id,
    name: thread.organization_name || "组织协作",
  } : null);
}

function createOrganizationThreadGroup(organization, threadButtons, threads) {
  const group = document.createElement("details");
  group.className = "organization-thread-group";
  group.open = true;
  const summary = document.createElement("summary");
  summary.className = "organization-thread-group-summary";
  const identity = document.createElement("span");
  identity.className = "organization-thread-group-identity";
  const icon = document.createElement("span");
  icon.className = "organization-thread-group-icon";
  icon.textContent = "群";
  icon.setAttribute("aria-hidden", "true");
  const copy = document.createElement("span");
  const title = document.createElement("strong");
  title.textContent = safeText(organization?.name, organization?.slug || "组织群聊");
  const subtitle = document.createElement("small");
  subtitle.textContent = threadButtons.length
    ? `${threadButtons.length} 个对话 · 全部组织 Agent 可读`
    : "群聊已建立 · 暂无对话";
  copy.append(title, subtitle);
  identity.append(icon, copy);
  const status = document.createElement("span");
  status.className = "organization-thread-group-status";
  const unreadCount = threads.filter(
    (thread) => !thread.virtual_organization_channel && thread.human_view_state === "unread",
  ).length;
  if (unreadCount) {
    const unread = document.createElement("span");
    unread.className = "organization-thread-group-unread";
    unread.textContent = String(unreadCount);
    unread.setAttribute("aria-label", `${unreadCount} 个对话尚未查看`);
    status.append(unread);
  }
  const chevron = document.createElement("span");
  chevron.className = "organization-thread-group-chevron";
  chevron.textContent = "⌄";
  chevron.setAttribute("aria-hidden", "true");
  status.append(chevron);
  summary.append(identity, status);
  const children = document.createElement("div");
  children.className = "organization-thread-children";
  if (threadButtons.length) {
    threadButtons.forEach((button) => children.append(button));
  } else {
    children.append(emptyState("群里还没有对话。通过这个组织发送的消息会集中显示在这里。"));
  }
  group.append(summary, children);
  return group;
}

function renderThreadList() {
  elements.threadList.replaceChildren();
  elements.threadArchiveLibrary.textContent = state.threadFilter === "archived"
    ? "‹ 返回我的对话"
    : "已归档对话";
  const threads = visibleThreadSummaries();
  const realThreadCount = threads.filter((thread) => !thread.virtual_organization_channel).length;
  const organizationGroups = new Map();
  elements.threadCount.textContent = `${realThreadCount} 个对话`;
  renderThreadParentSummary();
  if (!threads.length) {
    const hasAgents = Array.isArray(state.dashboard?.agents) && state.dashboard.agents.length > 0;
    if (state.threadQuery) {
      elements.threadList.append(emptyState("没有找到你有权查看且符合搜索条件的对话。"));
    } else if (state.threadFilter === "archived") {
      elements.threadList.append(emptyState("已归档对话会集中显示在这里，恢复后会回到“我的对话”。"));
    } else if (state.threadFilter === "exception") {
      elements.threadList.append(emptyState("当前授权范围内没有异常对话。"));
    } else if (hasAgents) {
      elements.threadList.append(emptyState("Agent 已连接或已授权，但目前还没有产生协作对话。"));
    } else {
      elements.threadList.append(emptyStateWithAction(
        "连接 Agent 后，它们之间的协作对话会出现在这里。",
        "去云驿连接 Agent",
        () => activateRoute("relay", "connections", { focusContent: true }),
      ));
    }
    return;
  }
  const fragment = document.createDocumentFragment();
  threads.forEach((thread) => {
    const organization = threadOrganization(thread);
    if (organization && !organizationGroups.has(String(organization.id))) {
      organizationGroups.set(String(organization.id), {
        organization,
        buttons: [],
        threads: [],
      });
    }
    if (organization) {
      organizationGroups.get(String(organization.id)).threads.push(thread);
    }
    if (thread.virtual_organization_channel) {
      return;
    }
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
    const recency = document.createElement("span");
    recency.className = "thread-list-recency";
    const time = document.createElement("span");
    time.className = "thread-list-time";
    time.textContent = thread.virtual_organization_channel
      ? "群聊已建立"
      : dateText(thread.latest_activity_at);
    recency.append(time);
    if (thread.human_view_state === "unread") {
      const unread = document.createElement("span");
      unread.className = "thread-unread-dot";
      unread.title = "你还没有查看这条对话的最新内容";
      unread.setAttribute("aria-label", "尚未查看");
      recency.append(unread);
    }
    top.append(topic, recency);

    const participants = document.createElement("span");
    participants.className = "thread-list-participants";
    const avatars = document.createElement("span");
    avatars.className = "thread-avatar-stack";
    [thread.latest_sender, thread.latest_recipient].filter(Boolean).forEach(
      (agent) => avatars.append(agentAvatar(agent)),
    );
    const names = document.createElement("span");
    names.className = "thread-participant-names";
    const channelOrganization = threadOrganization(thread);
    names.textContent = thread.virtual_organization_channel && channelOrganization
      ? `${Number(channelOrganization.member_count || 0)} 位成员 · ${Number(channelOrganization.agent_count || 0)} 个参与 Agent`
      : thread.channel_scope === "organization" && channelOrganization
        ? `${agentConversationLabel(thread.latest_sender)} → ${safeText(channelOrganization.name)} · 全体可读`
        : thread.latest_sender && thread.latest_recipient
          ? `${agentConversationLabel(thread.latest_sender)} → ${agentConversationLabel(thread.latest_recipient, { currentAsMe: true })}`
          : "参与者待确认";
    participants.append(avatars, names);

    const preview = document.createElement("span");
    preview.className = "thread-list-preview";
    preview.textContent = thread.latest_content_redacted
      ? "正文因当前审计角色而隐藏"
      : compactThreadContent(thread.latest_message_summary);

    const markers = document.createElement("span");
    markers.className = "thread-list-markers";
    const markerValues = [[
      thread.virtual_organization_channel ? "暂无消息" : `${thread.message_count} 条往来`,
      "conversation-count",
    ]];
    if (!thread.virtual_organization_channel) {
      markerValues.push([
        conversationStateLabel(thread.conversation_state),
        `conversation-state ${safeText(thread.conversation_state, "updated")}`,
      ]);
    }
    if (thread.attachment_count) markerValues.push([`附件 ${thread.attachment_count}`, ""]);
    if (thread.exception_count) markerValues.push([`异常 ${thread.exception_count}`, "exception"]);
    markerValues.forEach(([label, className]) => {
      const marker = document.createElement("span");
      marker.className = `thread-marker ${className}`.trim();
      marker.textContent = label;
      markers.append(marker);
    });
    button.append(top, participants, preview, markers);
    button.addEventListener("click", () => selectThread(String(thread.thread_id)));
    if (organization) {
      button.classList.add("organization-thread-child");
      organizationGroups.get(String(organization.id)).buttons.push(button);
    } else {
      fragment.append(button);
    }
  });
  const groupedFragment = document.createDocumentFragment();
  organizationGroups.forEach(({ organization, buttons, threads: groupThreads }) => {
    groupedFragment.append(createOrganizationThreadGroup(organization, buttons, groupThreads));
  });
  groupedFragment.append(fragment);
  elements.threadList.append(groupedFragment);
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
  selectAgent(String(agent.id), { updateHistory: false });
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
  label.textContent = `${agentOwnerLabel(agent)} · ${agentDisplayName(agent)} · ${agentTypeLabel(agent)}`;
  item.append(agentAvatar(agent), label);
  return item;
}

function readableStructuredValue(value) {
  if (value === null || value === undefined || value === "") {
    return "未提供";
  }
  if (["string", "number", "boolean"].includes(typeof value)) {
    return String(value);
  }
  if (Array.isArray(value) && value.every((item) => ["string", "number", "boolean"].includes(typeof item))) {
    return value.map(String).join("、");
  }
  return "包含更多结构化数据，可在下方展开查看";
}

function appendStructuredHumanSummary(message, body) {
  const summary = document.createElement("section");
  summary.className = "thread-structured-summary";
  const heading = document.createElement("strong");
  heading.textContent = "Agent 提供的结构化信息";
  summary.append(heading);
  const content = message.content_body;
  if (!content || typeof content !== "object" || Array.isArray(content)) {
    const note = document.createElement("p");
    note.textContent = Array.isArray(content)
      ? `这条消息包含 ${content.length} 项数据，可展开查看完整内容。`
      : readableStructuredValue(content);
    summary.append(note);
    body.append(summary);
    return;
  }

  const fieldLabels = {
    title: "标题",
    summary: "摘要",
    conclusion: "结论",
    message: "说明",
    instruction: "任务",
    result: "结果",
    status: "状态",
    next_step: "下一步",
    next_steps: "下一步",
  };
  const fields = Object.keys(fieldLabels)
    .filter((key) => Object.hasOwn(content, key))
    .slice(0, 6);
  if (!fields.length) {
    const note = document.createElement("p");
    note.textContent = `这条消息包含 ${Object.keys(content).length} 个结构化数据项，可展开查看完整内容。`;
    summary.append(note);
  } else {
    const grid = document.createElement("dl");
    grid.className = "thread-structured-grid";
    fields.forEach((key) => {
      const term = document.createElement("dt");
      term.textContent = fieldLabels[key];
      const detail = document.createElement("dd");
      detail.textContent = key === "status"
        ? statusLabel(content[key])
        : readableStructuredValue(content[key]);
      grid.append(term, detail);
    });
    summary.append(grid);
  }
  body.append(summary);
}

function appendAgentData(message, body) {
  const details = document.createElement("details");
  details.className = "thread-agent-data";
  const summary = document.createElement("summary");
  summary.textContent = message.content_format === "json"
    ? "查看 Agent 数据与技术信息（JSON）"
    : "查看 Agent 技术信息";
  summary.tabIndex = 0;
  summary.addEventListener("keydown", (event) => {
    if (!["Enter", " "].includes(event.key)) {
      return;
    }
    event.preventDefault();
    details.open = !details.open;
  });
  const grid = document.createElement("dl");
  grid.className = "thread-agent-data-grid";
  [
    ["消息格式", safeText(message.content_format, "text")],
    ["消息类型", safeText(message.message_type, "message")],
    ["消息编号", safeText(message.message_id)],
    ["要求确认收到", message.requires_ack ? "是" : "否"],
  ].forEach(([label, value]) => {
    const term = document.createElement("dt");
    term.textContent = label;
    const detail = document.createElement("dd");
    detail.textContent = value;
    grid.append(term, detail);
  });
  details.append(summary, grid);
  if (message.content_format === "json" && !message.content_redacted) {
    const rawLabel = document.createElement("strong");
    rawLabel.className = "thread-agent-data-label";
    rawLabel.textContent = "原始 JSON";
    const raw = document.createElement("pre");
    raw.className = "thread-agent-data-json";
    raw.textContent = safeText(message.content_body, "null");
    details.append(rawLabel, raw);
  }
  const note = document.createElement("p");
  note.className = "thread-agent-data-note";
  note.textContent = "这些信息用于 Agent 协作和问题排查，不代表任务已经完成。";
  details.append(note);
  body.append(details);
}

function renderThreadMessageContent(message, body) {
  if (message.content_redacted) {
    const content = document.createElement("p");
    content.className = "thread-redacted-content";
    content.textContent = "正文因当前审计角色而隐藏。";
    body.append(content);
    appendAgentData(message, body);
    return;
  }
  if (message.content_format === "json") {
    appendStructuredHumanSummary(message, body);
  } else {
    const heading = document.createElement("p");
    heading.className = "thread-content-format";
    heading.textContent = message.content_format === "markdown"
      ? "消息内容 · 已按安全文本显示"
      : "消息内容";
    const content = document.createElement("pre");
    const contentFormat = message.content_format === "markdown" ? "markdown" : "text";
    content.className = `thread-message-content thread-message-content-${contentFormat}`;
    content.textContent = safeText(message.content_body, "无正文");
    body.append(heading, content);
  }
  appendAgentData(message, body);
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
    const actions = document.createElement("div");
    actions.className = "thread-attachment-actions";
    const normalizedType = safeText(attachment.content_type, "").split(";", 1)[0].trim().toLowerCase();
    const attachmentId = encodeURIComponent(String(attachment.id));
    const downloadUrl = `/api/v1/orbit/attachments/${attachmentId}`;
    const previewUrl = `${downloadUrl}/preview`;

    if (normalizedType === "application/pdf") {
      const open = document.createElement("a");
      open.className = "thread-attachment-action";
      open.href = previewUrl;
      open.target = "_blank";
      open.rel = "noopener noreferrer";
      open.textContent = "打开 PDF";
      actions.append(open);
    } else if (normalizedType === "text/html") {
      const preview = document.createElement("button");
      preview.type = "button";
      preview.className = "thread-attachment-action";
      preview.textContent = "安全预览";
      preview.addEventListener("click", () => openAttachmentPreview(attachment));
      actions.append(preview);
    }

    const download = document.createElement("a");
    download.className = "thread-attachment-action";
    download.href = downloadUrl;
    download.download = safeText(attachment.filename, "attachment");
    download.textContent = "下载";
    actions.append(download);
    card.append(name, info, actions);
    list.append(card);
  });
  body.append(list);
}

function closeAttachmentPreview() {
  elements.attachmentPreviewFrame.removeAttribute("src");
  elements.attachmentPreviewDownload.removeAttribute("href");
  elements.attachmentPreviewMeta.textContent = "";
  if (elements.attachmentPreviewDialog.open) {
    elements.attachmentPreviewDialog.close();
  }
}

function openAttachmentPreview(attachment) {
  const attachmentId = encodeURIComponent(String(attachment.id));
  const downloadUrl = `/api/v1/orbit/attachments/${attachmentId}`;
  elements.attachmentPreviewTitle.textContent = safeText(attachment.filename, "预览附件");
  elements.attachmentPreviewMeta.textContent = `${safeText(attachment.content_type, "未知类型")} · ${formatFileSize(attachment.size)}`;
  elements.attachmentPreviewDownload.href = downloadUrl;
  elements.attachmentPreviewDownload.download = safeText(attachment.filename, "attachment");
  elements.attachmentPreviewFrame.src = `${downloadUrl}/preview`;
  elements.attachmentPreviewDialog.showModal();
  elements.attachmentPreviewDone.focus();
}

function renderTimelineEvent(message) {
  const event = document.createElement("article");
  event.className = "timeline-event";
  event.id = `message-${message.message_id}`;
  event.tabIndex = -1;
  const heading = document.createElement("strong");
  heading.textContent = `${messageTypeLabel(message.message_type)} · ${safeText(message.subject, "无主题事件")}`;
  const route = document.createElement("span");
  route.textContent = `发送自：${agentConversationLabel(message.sender)}；发送给：${agentConversationLabel(message.recipient, { currentAsMe: true })} · ${dateText(message.created_at)}`;
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
  const fromCurrentHuman = Boolean(message.sender?.owned_by_current_human);
  card.classList.toggle("from-current-human", fromCurrentHuman);
  const body = document.createElement("div");
  body.className = "thread-message-body";
  const identity = document.createElement("div");
  identity.className = "thread-message-identity";
  const sender = document.createElement("strong");
  sender.textContent = `发送自：${agentConversationLabel(message.sender)}`;
  const type = document.createElement("span");
  type.className = "thread-agent-type";
  type.textContent = `${agentTypeLabel(message.sender)} · ${messageTypeLabel(message.message_type)}`;
  const time = document.createElement("span");
  time.className = "thread-message-time";
  time.textContent = dateText(message.created_at);
  identity.append(sender, type, time);
  const route = document.createElement("div");
  route.className = "thread-message-route";
  const requestedResponderLabels = (message.requested_responders || []).map(
    (agent) => agentConversationLabel(agent),
  );
  route.textContent = message.channel_scope === "organization"
    ? `发送到：${safeText(message.organization_name, "组织协作")} · 全部组织 Agent 可读${requestedResponderLabels.length ? ` · 请 ${requestedResponderLabels.join("、")} 回复` : " · 无指定回复人"}`
    : `发送给：${agentConversationLabel(message.recipient, { currentAsMe: true })} · ${agentTypeLabel(message.recipient)}`;
  const subject = document.createElement("strong");
  subject.className = "thread-message-subject";
  subject.textContent = safeText(message.subject, "无主题消息");
  body.append(identity, route, subject);

  const states = document.createElement("div");
  states.className = "thread-message-states";
  const communication = document.createElement("span");
  communication.className = "thread-state-group";
  const communicationChip = chip(
    message.channel_scope === "organization" ? "organization_shared" : message.communication_state,
  );
  if (message.channel_scope === "organization") {
    communicationChip.textContent = `已同步给 ${Number(message.organization_recipient_count || 0)} 个 Agent`;
  }
  communication.append(
    document.createTextNode(message.channel_scope === "organization" ? "协作范围" : "送达情况"),
    communicationChip,
  );
  states.append(communication);
  if (repliedMessageIds.has(message.message_id)) {
    const replied = document.createElement("span");
    replied.className = "thread-state-group";
    replied.append(document.createTextNode("回复情况"), chip("replied"));
    states.append(replied);
  }
  if (message.work_state) {
    const work = document.createElement("span");
    work.className = "thread-state-group";
    work.append(document.createTextNode("任务进度"), chip(message.work_state));
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
    ? "由 Agent 提供 · 已按安全方式展示"
    : safeText(message.security_label);
  footer.append(trust);
  body.append(footer);
  if (fromCurrentHuman) {
    card.append(body, agentAvatar(message.sender, "agent-timeline-avatar"));
  } else {
    card.append(agentAvatar(message.sender, "agent-timeline-avatar"), body);
  }
  return card;
}

function renderThreadDetail(thread) {
  state.selectedThread = thread;
  elements.threadDetailEmpty.hidden = true;
  elements.threadDetail.hidden = false;
  elements.threadDetailTopic.textContent = safeText(thread.topic, "无主题对话");
  elements.threadDetailParticipants.replaceChildren();
  elements.messageList.replaceChildren();
  const chronologicalMessages = Array.isArray(thread.messages) ? thread.messages : [];
  const messages = [...chronologicalMessages].sort((left, right) => {
    const timeDifference = new Date(right.created_at).getTime() - new Date(left.created_at).getTime();
    return timeDifference || String(right.message_id).localeCompare(String(left.message_id));
  });
  elements.threadDetailCount.textContent = `完整对话 · ${messages.length} 条往来`;
  const firstMessage = chronologicalMessages[0];
  elements.threadDetailRoute.textContent = firstMessage
    ? firstMessage.channel_scope === "organization"
      ? `发送自：${agentConversationLabel(firstMessage.sender)}　　发送到：${safeText(firstMessage.organization_name, "组织协作")}（全部组织 Agent 可读）`
      : `发送自：${agentConversationLabel(firstMessage.sender)}　　给：${agentConversationLabel(firstMessage.recipient, { currentAsMe: true })}`
    : "发送自：—　　给：—";
  const failed = messages.some((message) => message.work_state === "failed" || message.message_type === "error");
  const completed = messages.some((message) => message.work_state === "completed");
  const pending = messages.some((message) => message.work_state === "pending");
  const detailState = failed ? "needs_attention" : completed ? "completed" : pending ? "in_progress" : "updated";
  elements.threadDetailState.className = `conversation-state-pill ${detailState}`;
  elements.threadDetailState.textContent = failed
    ? "需要关注"
    : completed
    ? "协作已完成"
    : pending
    ? "正在协作"
    : "对话进行中";
  const archived = Boolean(thread.archived_at) || state.threadFilter === "archived";
  elements.threadArchive.textContent = archived ? "恢复到我的对话" : "从我的对话删除";
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

async function markThreadViewed(threadId) {
  if (!state.csrfToken) {
    return;
  }
  const viewed = await requestJson(
    `/api/v1/orbit/threads/${encodeURIComponent(threadId)}/viewed`,
    { method: "POST", headers: { "X-CSRF-Token": state.csrfToken } },
  );
  const summary = state.threads.find((thread) => String(thread.thread_id) === String(threadId));
  if (summary) {
    summary.human_view_state = "viewed";
    summary.human_viewed_at = viewed?.viewed_at || new Date().toISOString();
  }
  if (state.selectedThread) {
    state.selectedThread.human_view_state = "viewed";
    state.selectedThread.human_viewed_at = viewed?.viewed_at || new Date().toISOString();
  }
  renderThreadList();
}

async function loadThreadDetail(threadId) {
  if (String(threadId).startsWith("organization:")) {
    const organizationId = String(threadId).slice("organization:".length);
    const organization = (state.dashboard?.organizations || []).find(
      (candidate) => String(candidate.id) === organizationId,
    );
    if (state.selectedThreadId !== String(threadId)) {
      return;
    }
    state.selectedThread = null;
    if (!organization) {
      setThreadDetailEmpty("无法打开这个组织群聊", "你可能已经离开组织，请刷新后重试。");
      return;
    }
    const participantCopy = Number(organization.agent_count || 0) > 0
      ? `${organization.agent_count} 个 Agent 已可参与。成员没有手动选择 Agent 时，系统会使用其默认 Agent。`
      : "群聊已经可见；成员连接并设置默认 Agent 后即可参与协作。";
    setThreadDetailEmpty(
      `${safeText(organization.name, organization.slug)} 群聊`,
      `${organization.member_count} 位成员。${participantCopy} 第一条群消息发送后，完整往来会显示在这里。`,
    );
    return;
  }
  setThreadDetailEmpty("正在读取对话", "只会显示你有权查看的内容，不会改变 Agent 的已读或处理状态。");
  try {
    const thread = await requestJson(`/api/v1/orbit/threads/${encodeURIComponent(threadId)}`);
    if (state.selectedThreadId !== String(threadId)) {
      return;
    }
    renderThreadDetail(thread);
    try {
      await markThreadViewed(threadId);
    } catch (_error) {
      // Keep the unread indicator when the separate Human-view update did not persist.
    }
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
  if (isMobileWorkspace()) {
    elements.threadMobileBack.scrollIntoView({ block: "start" });
    elements.threadMobileBack.focus({ preventScroll: true });
  } else {
    elements.threadDetailTopic.focus?.({ preventScroll: true });
  }
}

function clearThreadSelection({ updateHistory = true } = {}) {
  state.selectedThreadId = "";
  state.selectedThread = null;
  updateThreadWorkspaceMode();
  renderThreadList();
  setThreadDetailEmpty("选择一条协作对话", "选择一个对话后，这个话题下的全部往来会按时间显示在这里。");
  if (updateHistory) {
    history.pushState({ module: "orbit", section: "communications" }, "", threadRouteUrl());
  }
  resetMobileLayerScroll();
}

function threadListEndpoint() {
  const parameters = new URLSearchParams({ limit: "200" });
  if (state.threadQuery) {
    parameters.set("query", state.threadQuery);
  }
  if (state.threadFilter === "archived") {
    parameters.set("archived", "true");
  }
  return `/api/v1/orbit/threads?${parameters.toString()}`;
}

function openThreadArchiveDialog(thread) {
  elements.threadArchiveId.value = String(thread.thread_id);
  elements.threadArchiveSummary.textContent = `“${safeText(thread.topic, "无主题对话")}”将从你的“我的对话”中隐藏。服务器消息不会删除。`;
  elements.threadArchiveResult.textContent = "";
  elements.threadArchiveDialog.showModal();
}

function closeThreadArchiveDialog() {
  elements.threadArchiveDialog.close();
  elements.threadArchiveForm.reset();
  elements.threadArchiveResult.textContent = "";
}

async function archiveThread(threadId) {
  await requestJson(`/api/v1/orbit/threads/${encodeURIComponent(threadId)}/archive`, {
    method: "PUT",
    headers: { "X-CSRF-Token": state.csrfToken },
  });
  if (state.selectedThreadId === String(threadId)) {
    clearThreadSelection({ updateHistory: true });
  }
  await loadThreads({ loadSelection: false });
}

async function restoreThread(threadId) {
  await requestJson(`/api/v1/orbit/threads/${encodeURIComponent(threadId)}/archive`, {
    method: "DELETE",
    headers: { "X-CSRF-Token": state.csrfToken },
  });
  if (state.selectedThreadId === String(threadId)) {
    clearThreadSelection({ updateHistory: true });
  }
  await loadThreads({ loadSelection: false });
}

async function loadThreads({ loadSelection = true } = {}) {
  const threads = await requestJson(threadListEndpoint());
  state.threads = Array.isArray(threads) ? threads : [];
  renderThreadOrganizationOptions();
  renderThreadList();
  if (loadSelection && state.selectedThreadId) {
    await loadThreadDetail(state.selectedThreadId);
  } else if (!state.selectedThreadId) {
    setThreadDetailEmpty("选择一条协作对话", "选择一个对话后，这个话题下的全部往来会按时间显示在这里。");
  }
}

function renderSecurity(security) {
  const password = security.password_configured ? "密码已设置" : "需先找回账户设置密码";
  const mfa = security.mfa_enabled ? "双重验证已开启" : "双重验证未开启";
  const keys = `${safeText(security.active_human_keys, "0")} 个旧版集成凭证`;
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
  elements.topHumanName.textContent = safeText(user.display_name, "星轨用户");
  elements.topHumanAvatar.textContent = "我";
  elements.profileName.textContent = safeText(user.display_name, "未设置");
  elements.profileUsername.textContent = safeText(user.username, "未设置");
  elements.profileEmail.textContent = safeText(user.email);
  elements.profileTimezone.textContent = safeText(
    Intl.DateTimeFormat().resolvedOptions().timeZone,
    "此设备未提供",
  );
  const pendingApprovals = Number(dashboard.metrics?.pending_approval_count || 0);
  elements.approvalQuickCount.textContent = String(pendingApprovals);
  elements.approvalQuickCount.hidden = pendingApprovals === 0;
  elements.approvalMobileCount.textContent = String(pendingApprovals);
  const pendingTasks = Number(dashboard.metrics?.pending_task_count || 0);
  elements.taskQuickCount.textContent = String(pendingTasks);
  elements.taskMobileCount.textContent = String(pendingTasks);
  renderOrganizations(organizations);
  renderAgents(agents);
  renderTasks(tasks);
  renderApprovals(approvals);
}

async function loadDashboard() {
  elements.refresh.disabled = true;
  setConnection("正在同步数据", "loading", "同步中");
  try {
    const [dashboard, connectors, security, threads, invitations] = await Promise.all([
      requestJson("/api/v1/orbit/dashboard"),
      requestJson("/api/v1/orbit/connectors"),
      requestJson("/api/v1/orbit/security"),
      requestJson(threadListEndpoint()),
      requestJson("/api/v1/orbit/organization-invitations"),
    ]);
    state.connectors = Array.isArray(connectors.items) ? connectors.items : [];
    state.threads = Array.isArray(threads) ? threads : [];
    renderDashboard(dashboard);
    renderPendingOrganizationInvitations(Array.isArray(invitations.items) ? invitations.items : []);
    renderConnectors(state.connectors);
    renderSecurity(security);
    renderThreadOrganizationOptions();
    renderThreadList();
    if (state.selectedThreadId) {
      await loadThreadDetail(state.selectedThreadId);
    } else {
      setThreadDetailEmpty("选择一条协作对话", "选择一个对话后，这个话题下的全部往来会在这里显示，最新内容排在最上面。");
    }
    elements.welcomeView.hidden = true;
    elements.workspaceView.hidden = false;
    const connectedAgentCount = Number(dashboard.metrics?.connected_agent_count || 0);
    setConnection(
      `${connectedAgentCount} 个 Agent 在线`,
      connectedAgentCount > 0 ? "success" : "",
      `${connectedAgentCount} 个 Agent`,
    );
    await maybeOpenRequestedPairing();
    await maybePreviewOrganizationInvitation();
  } catch (error) {
    setConnection("数据同步失败", "error", "同步失败");
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
  if (!selfService) {
    setFormStatus("当前环境尚未开通邮箱登录，请联系管理员。", "error");
  }
}

async function discoverEnterpriseOidc() {
  const email = elements.loginEmail.value.trim();
  elements.oidcOptions.replaceChildren();
  if (!email || !email.includes("@")) {
    setFormStatus("请先填写单位邮箱，再选择单位统一登录。", "error");
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
      setFormStatus("这个邮箱所在单位尚未开通统一登录。", "error");
      return;
    }
    providers.forEach((provider) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "quiet-button";
      button.textContent = `使用 ${safeText(provider.display_name, "单位工作账号")} 登录`;
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
    setFormStatus("请选择你的单位登录入口继续。", "success");
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
  setFormStatus("正在验证邮箱、密码和双重验证码…");
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
  elements.registerUsername.value = "";
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
        username: elements.registerUsername.value.trim().toLowerCase(),
        display_name: elements.registerName.value.trim(),
        password: elements.registerPassword.value,
      }),
    });
    state.csrfToken = browserSession.csrf_token;
    closeRegisterDialog();
    await loadDashboard();
    setFormStatus("账户已创建。建议现在开启双重验证。", "success");
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
    setFormStatus("密码已重设，其他浏览器会话和旧版集成凭证已失效。", "success");
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
    elements.mfaResult.textContent = "双重验证已开启。恢复码每枚只能使用一次，请保存后再关闭窗口。";
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
    elements.keyResult.textContent = "新凭证仅显示一次；以前的旧版集成凭证已全部失效。";
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
    closeAttachmentPreview();
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
    if (state.authConfig?.self_service_enabled) {
      elements.loginEmail.focus();
    }
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
    elements.approvalResult.textContent = "请输入当前密码（或有效的旧版集成凭证）。";
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

elements.loginForm.addEventListener("submit", loginHuman);
elements.attachmentPreviewClose.addEventListener("click", closeAttachmentPreview);
elements.attachmentPreviewDone.addEventListener("click", closeAttachmentPreview);
elements.attachmentPreviewDialog.addEventListener("close", () => {
  elements.attachmentPreviewFrame.removeAttribute("src");
  elements.attachmentPreviewDownload.removeAttribute("href");
  elements.attachmentPreviewMeta.textContent = "";
});
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
  elements.recoveryResult.textContent = "重设密码将退出其他浏览器，并使所有旧版集成凭证失效。";
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
    setConnection(error.message, "error");
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
  setThreadDetailEmpty("选择一条协作对话", "搜索结果只包含你有权查看的内容。");
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
  button.addEventListener("click", async () => {
    if (button.getAttribute("aria-disabled") === "true") {
      return;
    }
    const requestedFilter = button.dataset.threadFilter || "all";
    state.threadFilter = requestedFilter === "archived" && state.threadFilter === "archived"
      ? "all"
      : requestedFilter;
    elements.threadFilters.forEach((item) => {
      const active = (item.dataset.threadFilter || "all") === state.threadFilter;
      item.classList.toggle("active", active);
      if (item.getAttribute("aria-disabled") !== "true") {
        item.setAttribute("aria-pressed", String(active));
      }
    });
    state.selectedThreadId = "";
    state.selectedThread = null;
    setThreadDetailEmpty(
      "选择一条协作对话",
      state.threadFilter === "archived"
        ? "这里集中保存你从“我的对话”移出的完整对话，可随时恢复。"
        : "当前列表已按所选范围筛选。",
    );
    updateThreadWorkspaceMode();
    if (requestedFilter === "archived" && isMobileWorkspace()) {
      activateRoute("orbit", "communications", { focusContent: true });
    }
    try {
      await loadThreads({ loadSelection: false });
    } catch (_error) {
      elements.threadList.replaceChildren(emptyState("对话列表读取失败，请稍后重试。"));
    }
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
elements.threadArchive.addEventListener("click", async () => {
  if (!state.selectedThreadId || !state.selectedThread) {
    return;
  }
  if (Boolean(state.selectedThread.archived_at) || state.threadFilter === "archived") {
    try {
      await restoreThread(state.selectedThreadId);
    } catch (_error) {
      setThreadDetailEmpty("暂时无法恢复", "请稍后重试，这条对话仍保留在已归档对话中。");
    }
    return;
  }
  openThreadArchiveDialog(state.selectedThread);
});
elements.threadArchiveForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const threadId = elements.threadArchiveId.value;
  if (!threadId) {
    return;
  }
  elements.threadArchiveSubmit.disabled = true;
  elements.threadArchiveResult.textContent = "正在整理…";
  try {
    await archiveThread(threadId);
    closeThreadArchiveDialog();
  } catch (_error) {
    elements.threadArchiveResult.textContent = "暂时无法移出，请稍后重试。";
  } finally {
    elements.threadArchiveSubmit.disabled = false;
  }
});
[elements.threadArchiveClose, elements.threadArchiveCancel].forEach((button) => {
  button.addEventListener("click", () => closeThreadArchiveDialog());
});
elements.threadLatest.addEventListener("click", () => {
  elements.messageList.firstElementChild?.scrollIntoView({ behavior: "smooth", block: "start" });
});
elements.agentSearchInput.addEventListener("input", () => {
  state.agentQuery = elements.agentSearchInput.value.trim();
  renderAgentBrowser(state.dashboard?.agents || []);
  history.replaceState(
    { module: "relay", section: "agents", agent: state.selectedAgentId || null },
    "",
    agentRouteUrl(),
  );
});
[elements.agentBrowserNew, elements.agentOverviewNew].forEach((button) => {
  button.addEventListener("click", () => openPairingDialog());
});
elements.agentMobileBack.addEventListener("click", () => clearAgentSelection());
elements.agentDetailTabs.forEach((button) => {
  button.addEventListener("click", () => {
    state.agentTab = button.dataset.agentTab || "summary";
    renderAgentTab();
    history.replaceState(
      { module: "relay", section: "agents", agent: state.selectedAgentId, agentTab: state.agentTab },
      "",
      agentRouteUrl(),
    );
  });
});
elements.agentBrowserList.addEventListener("keydown", (event) => {
  if (!["ArrowDown", "ArrowUp"].includes(event.key)) return;
  const items = Array.from(elements.agentBrowserList.querySelectorAll(".agent-browser-item"));
  const index = items.indexOf(document.activeElement);
  if (index < 0 || items.length < 2) return;
  event.preventDefault();
  const direction = event.key === "ArrowDown" ? 1 : -1;
  items[(index + direction + items.length) % items.length].focus();
});
elements.agentReturnThread.addEventListener("click", () => {
  const threadId = new URLSearchParams(window.location.search).get("returnThread");
  if (threadId) openRelatedThread(threadId);
});
elements.agentReconnect.addEventListener("click", () => {
  const agent = state.selectedAgent;
  if (!agent || agent.role !== "owner") return;
  const connector = state.connectors.find(
    (item) => String(item.agent?.id) === String(agent.id) && item.is_current,
  ) || state.connectors.find((item) => String(item.agent?.id) === String(agent.id));
  openPairingDialog("", "", agent, safeText(connector?.connector_type, agent.current_connector_type || ""));
});
elements.agentRename.addEventListener("click", () => {
  if (state.selectedAgent?.role === "owner") openHandleDialog(state.selectedAgent);
});
elements.agentSetDefault.addEventListener("click", setSelectedAgentAsDefault);
elements.agentDisconnect.addEventListener("click", () => {
  const agent = state.selectedAgent;
  if (!agent || agent.role !== "owner") return;
  const connector = state.connectors.find(
    (item) => String(item.agent?.id) === String(agent.id)
      && item.is_current && item.status === "active",
  );
  if (connector) openRevokeDialog(connector);
});
elements.agentDelete.addEventListener("click", () => {
  if (state.selectedAgent?.role === "owner") openDeleteAgentDialog(state.selectedAgent);
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
elements.pairingHandle.addEventListener("input", updatePairingHandleHelp);
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
elements.organizationInvitationForm.addEventListener("submit", acceptOrganizationInvitation);
elements.organizationInvitationClose.addEventListener("click", closeOrganizationInvitationDialog);
elements.organizationInvitationCancel.addEventListener("click", closeOrganizationInvitationDialog);
elements.organizationInvitationDialog.addEventListener("close", closeOrganizationInvitationDialog);
elements.organizationInviteForm.addEventListener("submit", inviteOrganizationMember);
elements.organizationAgentAdd.addEventListener("click", () => changeOwnedOrganizationAgent(null, "assign"));
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
  elements.keyResult.textContent = "更换后，以前的旧版集成凭证将立即失效。";
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
  applyAgentRouteParameters(parameters);
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
      setThreadDetailEmpty("选择一条协作对话", "选择一个对话后，这个话题下的全部往来会按时间显示在这里。");
    }
  } else if (state.activeModule === "relay" && state.activeSection === "agents") {
    renderAgents(state.dashboard?.agents || []);
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
