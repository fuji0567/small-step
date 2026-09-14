const apiBase = "/api/v1";
const accessTokenStorageKey = "small-step.access-token";
const lowConfidenceThreshold = 0.7;

const state = {
  schoolId: null,
  schools: [],
  children: [],
  allChildren: [],
  lineLinkInvitations: [],
  teachers: [],
  edgeDevices: [],
  records: [],
  historyRecords: [],
  notifications: [],
  audioJobs: [],
  auditEvents: [],
  runtimeReadiness: null,
  voiceConsent: null,
  selectedRecordId: null,
  manualRecordMode: false,
  reschedulingNotificationId: null,
  editingChildId: null,
  activeView: "home",
  authConfig: null,
  accessToken: sessionStorage.getItem(accessTokenStorageKey),
  isSchoolAdmin: false,
  currentTeacherId: null,
};

const elements = {
  loginScreen: document.querySelector("#login-screen"),
  loginForm: document.querySelector("#login-form"),
  loginEmail: document.querySelector("#login-email"),
  loginPassword: document.querySelector("#login-password"),
  loginButton: document.querySelector("#login-button"),
  loginNotice: document.querySelector("#login-notice"),
  bootstrapPanel: document.querySelector("#bootstrap-panel"),
  bootstrapForm: document.querySelector("#bootstrap-form"),
  bootstrapSchoolSelect: document.querySelector("#bootstrap-school-select"),
  bootstrapName: document.querySelector("#bootstrap-name"),
  bootstrapButton: document.querySelector("#bootstrap-button"),
  appShell: document.querySelector("#app-shell"),
  logoutButton: document.querySelector("#logout-button"),
  schoolSelect: document.querySelector("#school-select"),
  schoolSettingsNavButton: document.querySelector("#school-settings-nav-button"),
  schoolSettingsView: document.querySelector("#school-settings-view"),
  schoolSettingsForm: document.querySelector("#school-settings-form"),
  schoolDigestTimeInput: document.querySelector("#school-digest-time-input"),
  schoolTimezoneNote: document.querySelector("#school-timezone-note"),
  schoolDigestTimeSaveButton: document.querySelector("#school-digest-time-save-button"),
  reloadButton: document.querySelector("#reload-button"),
  notice: document.querySelector("#notice"),
  loadingIndicator: document.querySelector("#loading-indicator"),
  recordCount: document.querySelector("#record-count"),
  recordList: document.querySelector("#record-list"),
  manualRecordOpenButton: document.querySelector("#manual-record-open-button"),
  manualRecordForm: document.querySelector("#manual-record-form"),
  manualRecordChildSelect: document.querySelector("#manual-record-child-select"),
  manualRecordTeacherField: document.querySelector("#manual-record-teacher-field"),
  manualRecordTeacherSelect: document.querySelector("#manual-record-teacher-select"),
  manualRecordCategorySelect: document.querySelector("#manual-record-category-select"),
  manualRecordOccurredAtInput: document.querySelector("#manual-record-occurred-at-input"),
  manualRecordSummaryInput: document.querySelector("#manual-record-summary-input"),
  manualRecordPromptInput: document.querySelector("#manual-record-prompt-input"),
  manualRecordCancelButton: document.querySelector("#manual-record-cancel-button"),
  manualRecordCreateButton: document.querySelector("#manual-record-create-button"),
  emptyState: document.querySelector("#empty-state"),
  reviewForm: document.querySelector("#review-form"),
  recordMeta: document.querySelector("#record-meta"),
  recordConfidenceWarning: document.querySelector("#record-confidence-warning"),
  recordCategory: document.querySelector("#record-category"),
  childSelect: document.querySelector("#child-select"),
  summaryInput: document.querySelector("#summary-input"),
  summaryCount: document.querySelector("#summary-count"),
  promptInput: document.querySelector("#prompt-input"),
  promptCount: document.querySelector("#prompt-count"),
  scheduledForEnabled: document.querySelector("#scheduled-for-enabled"),
  scheduledForInput: document.querySelector("#scheduled-for-input"),
  rejectButton: document.querySelector("#reject-button"),
  approveButton: document.querySelector("#approve-button"),
  navButtons: document.querySelectorAll(".nav-button"),
  reviewNavCount: document.querySelector("#review-nav-count"),
  notificationNavCount: document.querySelector("#notification-nav-count"),
  childInvitationNavCount: document.querySelector("#child-invitation-nav-count"),
  homeView: document.querySelector("#home-view"),
  reviewView: document.querySelector("#review-view"),
  recordHistoryView: document.querySelector("#record-history-view"),
  notificationsView: document.querySelector("#notifications-view"),
  audioJobsView: document.querySelector("#audio-jobs-view"),
  childrenView: document.querySelector("#children-view"),
  teachersView: document.querySelector("#teachers-view"),
  edgeDevicesView: document.querySelector("#edge-devices-view"),
  voiceConsentView: document.querySelector("#voice-consent-view"),
  homeReviewCount: document.querySelector("#home-review-count"),
  homePendingCount: document.querySelector("#home-pending-count"),
  homeSentCount: document.querySelector("#home-sent-count"),
  homeWaitingGuardianLinkCount: document.querySelector("#home-waiting-guardian-link-count"),
  homeActions: document.querySelectorAll("[data-view-target]"),
  notificationCount: document.querySelector("#notification-count"),
  notificationList: document.querySelector("#notification-list"),
  notificationFilterForm: document.querySelector("#notification-filter-form"),
  notificationStatusSelect: document.querySelector("#notification-status-select"),
  notificationSearch: document.querySelector("#notification-search"),
  notificationFilterResetButton: document.querySelector("#notification-filter-reset-button"),
  audioJobCount: document.querySelector("#audio-job-count"),
  audioJobList: document.querySelector("#audio-job-list"),
  childCount: document.querySelector("#child-count"),
  childForm: document.querySelector("#child-form"),
  childNameInput: document.querySelector("#child-name-input"),
  childCreateButton: document.querySelector("#child-create-button"),
  childRoleNote: document.querySelector("#child-role-note"),
  childList: document.querySelector("#child-list"),
  recordHistoryCount: document.querySelector("#record-history-count"),
  recordHistoryFilterForm: document.querySelector("#record-history-filter-form"),
  recordHistorySearch: document.querySelector("#record-history-search"),
  recordHistoryChildSelect: document.querySelector("#record-history-child-select"),
  recordHistoryStatusSelect: document.querySelector("#record-history-status-select"),
  recordHistoryCategorySelect: document.querySelector("#record-history-category-select"),
  recordHistoryFrom: document.querySelector("#record-history-from"),
  recordHistoryTo: document.querySelector("#record-history-to"),
  recordHistoryResetButton: document.querySelector("#record-history-reset-button"),
  recordHistoryExportButton: document.querySelector("#record-history-export-button"),
  recordHistoryList: document.querySelector("#record-history-list"),
  inviteResult: document.querySelector("#invite-result"),
  inviteChildName: document.querySelector("#invite-child-name"),
  inviteExpiration: document.querySelector("#invite-expiration"),
  inviteCode: document.querySelector("#invite-code"),
  copyInviteCodeButton: document.querySelector("#copy-invite-code-button"),
  guardianArchiveResult: document.querySelector("#guardian-archive-result"),
  guardianArchiveChildName: document.querySelector("#guardian-archive-child-name"),
  guardianArchiveExpiration: document.querySelector("#guardian-archive-expiration"),
  guardianArchiveUrl: document.querySelector("#guardian-archive-url"),
  copyGuardianArchiveUrlButton: document.querySelector("#copy-guardian-archive-url-button"),
  teachersNavButton: document.querySelector("#teachers-nav-button"),
  teacherCount: document.querySelector("#teacher-count"),
  teacherForm: document.querySelector("#teacher-form"),
  teacherNameInput: document.querySelector("#teacher-name-input"),
  teacherEmailInput: document.querySelector("#teacher-email-input"),
  teacherCreateButton: document.querySelector("#teacher-create-button"),
  teacherList: document.querySelector("#teacher-list"),
  edgeDevicesNavButton: document.querySelector("#edge-devices-nav-button"),
  edgeDeviceCount: document.querySelector("#edge-device-count"),
  edgeDeviceForm: document.querySelector("#edge-device-form"),
  edgeDeviceNameInput: document.querySelector("#edge-device-name-input"),
  edgeDeviceTeacherSelect: document.querySelector("#edge-device-teacher-select"),
  edgeDeviceCreateButton: document.querySelector("#edge-device-create-button"),
  edgeDeviceKeyResult: document.querySelector("#edge-device-key-result"),
  edgeDeviceKeyTitle: document.querySelector("#edge-device-key-title"),
  edgeDeviceApiKey: document.querySelector("#edge-device-api-key"),
  copyEdgeDeviceKeyButton: document.querySelector("#copy-edge-device-key-button"),
  edgeDeviceList: document.querySelector("#edge-device-list"),
  runtimeNavButton: document.querySelector("#runtime-nav-button"),
  runtimeView: document.querySelector("#runtime-view"),
  runtimeOverallStatus: document.querySelector("#runtime-overall-status"),
  runtimeDatabaseStatus: document.querySelector("#runtime-database-status"),
  runtimeDatabaseNote: document.querySelector("#runtime-database-note"),
  runtimeMigrationStatus: document.querySelector("#runtime-migration-status"),
  runtimeMigrationNote: document.querySelector("#runtime-migration-note"),
  runtimeAudioModeStatus: document.querySelector("#runtime-audio-mode-status"),
  runtimeAudioModeNote: document.querySelector("#runtime-audio-mode-note"),
  runtimeStorageStatus: document.querySelector("#runtime-storage-status"),
  runtimeStorageNote: document.querySelector("#runtime-storage-note"),
  runtimeLlmStatus: document.querySelector("#runtime-llm-status"),
  runtimeLlmNote: document.querySelector("#runtime-llm-note"),
  runtimeGpuWorkerStatus: document.querySelector("#runtime-gpu-worker-status"),
  runtimeGpuWorkerNote: document.querySelector("#runtime-gpu-worker-note"),
  runtimeLineStatus: document.querySelector("#runtime-line-status"),
  runtimeLineNote: document.querySelector("#runtime-line-note"),
  runtimeLineWorkerStatus: document.querySelector("#runtime-line-worker-status"),
  runtimeLineWorkerNote: document.querySelector("#runtime-line-worker-note"),
  runtimeRefreshButton: document.querySelector("#runtime-refresh-button"),
  auditEventsNavButton: document.querySelector("#audit-events-nav-button"),
  auditEventsView: document.querySelector("#audit-events-view"),
  auditEventCount: document.querySelector("#audit-event-count"),
  auditEventsFilterForm: document.querySelector("#audit-events-filter-form"),
  auditEventsActionSelect: document.querySelector("#audit-events-action-select"),
  auditEventsFrom: document.querySelector("#audit-events-from"),
  auditEventsTo: document.querySelector("#audit-events-to"),
  auditEventsFilterResetButton: document.querySelector("#audit-events-filter-reset-button"),
  auditEventsExportButton: document.querySelector("#audit-events-export-button"),
  auditEventList: document.querySelector("#audit-event-list"),
  voiceConsentStatus: document.querySelector("#voice-consent-status"),
  voiceConsentForm: document.querySelector("#voice-consent-form"),
  voiceConsentCheckbox: document.querySelector("#voice-consent-checkbox"),
  voiceConsentRetentionDays: document.querySelector("#voice-consent-retention-days"),
  voiceConsentSubmitButton: document.querySelector("#voice-consent-submit-button"),
  voiceConsentRevokeButton: document.querySelector("#voice-consent-revoke-button"),
  confirmationDialog: document.querySelector("#confirmation-dialog"),
  confirmationTitle: document.querySelector("#confirmation-title"),
  confirmationMessage: document.querySelector("#confirmation-message"),
  confirmationCancel: document.querySelector("#confirmation-cancel"),
  confirmationConfirm: document.querySelector("#confirmation-confirm"),
};

const textLimit = 4000;
let loadingOperationCount = 0;
let confirmationResolve = null;
let confirmationReturnFocus = null;

// 先生管理者だけが使えるビュー。一般の先生には、ナビもビュー本体もDOMから取り除きます。
const schoolAdminOnlyViews = [
  { view: "school-settings", navButton: elements.schoolSettingsNavButton, section: elements.schoolSettingsView },
  { view: "teachers", navButton: elements.teachersNavButton, section: elements.teachersView },
  { view: "edge-devices", navButton: elements.edgeDevicesNavButton, section: elements.edgeDevicesView },
  { view: "runtime", navButton: elements.runtimeNavButton, section: elements.runtimeView },
  { view: "audit-events", navButton: elements.auditEventsNavButton, section: elements.auditEventsView },
];
const detachedAdminNodes = new Map();

function detachAdminNode(node) {
  if (detachedAdminNodes.has(node)) return;
  const placeholder = document.createComment(node.id);
  detachedAdminNodes.set(node, placeholder);
  node.replaceWith(placeholder);
}

function attachAdminNode(node) {
  const placeholder = detachedAdminNodes.get(node);
  if (!placeholder) return;
  detachedAdminNodes.delete(node);
  placeholder.replaceWith(node);
}

function applySchoolAdminVisibility() {
  for (const { navButton, section } of schoolAdminOnlyViews) {
    navButton.hidden = !state.isSchoolAdmin;
    if (state.isSchoolAdmin) {
      attachAdminNode(navButton);
      attachAdminNode(section);
    } else {
      detachAdminNode(navButton);
      detachAdminNode(section);
    }
  }
}

function isSchoolAdminOnlyView(view) {
  return schoolAdminOnlyViews.some((entry) => entry.view === view);
}

function setNotice(message, isError = false) {
  elements.notice.textContent = message;
  elements.notice.hidden = !message;
  elements.notice.classList.toggle("is-error", isError);
  elements.notice.setAttribute("role", isError ? "alert" : "status");
}

function setLoginNotice(message, isError = false) {
  elements.loginNotice.textContent = message;
  elements.loginNotice.hidden = !message;
  elements.loginNotice.classList.toggle("is-error", isError);
  elements.loginNotice.setAttribute("role", isError ? "alert" : "status");
}

function setLoading(isLoading) {
  loadingOperationCount = Math.max(0, loadingOperationCount + (isLoading ? 1 : -1));
  const isBusy = loadingOperationCount > 0;
  elements.loadingIndicator.hidden = !isBusy;
  elements.appShell.setAttribute("aria-busy", String(isBusy));
}

async function withLoading(operation) {
  setLoading(true);
  try {
    return await operation();
  } finally {
    setLoading(false);
  }
}

function updateCharacterCount(input, output) {
  const maximum = input.maxLength > 0 ? input.maxLength : textLimit;
  output.textContent = `${input.value.length.toLocaleString("ja-JP")} / ${maximum.toLocaleString("ja-JP")}文字`;
}

function updateReviewCharacterCounts() {
  updateCharacterCount(elements.summaryInput, elements.summaryCount);
  updateCharacterCount(elements.promptInput, elements.promptCount);
}

const localIconPaths = Object.freeze({
  default: ["M12 2a10 10 0 1 0 0 20a10 10 0 0 0 0-20", "M12 8v4", "M12 16h.01"],
  admin_panel_settings: ["M4 5h16", "M4 12h16", "M4 19h16", "M8 3v4", "M16 10v4", "M11 17v4"],
  block: ["M5 5l14 14", "M19 5L5 19"],
  check: ["M5 12l4 4L19 6"],
  checklist: ["M9 6h10", "M9 12h10", "M9 18h10", "M4 6l1.5 1.5L7.5 4.5", "M4 12l1.5 1.5L7.5 10.5", "M4 18l1.5 1.5L7.5 16.5"],
  child_care: ["M12 5a2 2 0 1 0 0 4a2 2 0 0 0 0-4", "M5 20c0-3 3-6 7-6s7 3 7 6", "M7 12l5 2 5-2"],
  close: ["M6 6l12 12", "M18 6L6 18"],
  content_copy: ["M9 9h11v11H9z", "M4 4h11v11H4z"],
  description: ["M6 3h9l3 3v15H6z", "M15 3v4h4", "M9 12h6", "M9 16h6"],
  download: ["M12 3v12", "M7 10l5 5 5-5", "M5 21h14"],
  edit: ["M4 20h4L19 9l-4-4L4 16z", "M13 7l4 4"],
  edit_note: ["M5 4h10", "M5 9h7", "M5 14h5", "M14 20h4l2-2-4-4-2 2z", "M16 16l2 2"],
  fact_check: ["M6 3h9l3 3v15H6z", "M15 3v4h4", "M9 13l2 2 4-4", "M9 18h6"],
  filter_alt: ["M4 5h16", "M7 12h10", "M10 19h4"],
  graphic_eq: ["M5 5v14", "M10 9v6", "M15 3v18", "M20 7v10"],
  group: ["M8 11a3 3 0 1 0 0-6a3 3 0 0 0 0 6", "M2 21c0-4 2.5-7 6-7s6 3 6 7", "M17 10a2.5 2.5 0 1 0 0-5", "M16 14c3.5 0 6 2.5 6 6"],
  group_add: ["M8 11a3 3 0 1 0 0-6a3 3 0 0 0 0 6", "M2 21c0-4 2.5-7 6-7s6 3 6 7", "M18 8v6", "M15 11h6"],
  history: ["M3 12a9 9 0 1 0 3-6.7", "M3 4v5h5", "M12 7v5l3 2"],
  home: ["M3 10.5L12 3l9 7.5V21h-6v-6H9v6H3z"],
  key: ["M7 15a4 4 0 1 1 2.8-6.8A4 4 0 0 1 7 15", "M10 12h11", "M18 12v3", "M15 12v2"],
  link: ["M10 13a5 5 0 0 0 7.1.1l2-2a5 5 0 0 0-7.1-7.1l-1.2 1.2", "M14 11a5 5 0 0 0-7.1-.1l-2 2a5 5 0 0 0 7.1 7.1l1.2-1.2", "M8 12h8"],
  link_off: ["M4 4l16 16", "M10 13a5 5 0 0 0 7.1.1l2-2a5 5 0 0 0-5.4-8.2", "M14 11a5 5 0 0 0-7.1-.1l-2 2a5 5 0 0 0 5.4 8.2"],
  login: ["M10 17l5-5-5-5", "M15 12H3", "M21 3v18h-8"],
  logout: ["M14 7l5 5-5 5", "M19 12H7", "M7 3H3v18h4"],
  mic: ["M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3", "M5 11a7 7 0 0 0 14 0", "M12 18v3", "M8 21h8"],
  notifications: ["M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9", "M10 21h4"],
  person_add: ["M9 11a3 3 0 1 0 0-6a3 3 0 0 0 0 6", "M3 21c0-4 2.5-7 6-7s6 3 6 7", "M19 8v6", "M16 11h6"],
  person_remove: ["M9 11a3 3 0 1 0 0-6a3 3 0 0 0 0 6", "M3 21c0-4 2.5-7 6-7s6 3 6 7", "M16 11h6"],
  privacy_tip: ["M12 3l7 3v5c0 5-3 8-7 10c-4-2-7-5-7-10V6z", "M12 9v4", "M12 16h.01"],
  refresh: ["M20 11a8 8 0 1 0 2 5", "M20 4v7h-7"],
  schedule: ["M12 2a10 10 0 1 0 0 20a10 10 0 0 0 0-20", "M12 7v5l3 2"],
  search: ["M11 4a7 7 0 1 0 0 14a7 7 0 0 0 0-14", "M16 16l4 4"],
});

function createButtonIcon(iconName) {
  const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  icon.classList.add("button-icon");
  icon.setAttribute("aria-hidden", "true");
  icon.setAttribute("viewBox", "0 0 24 24");
  icon.setAttribute("fill", "none");
  icon.setAttribute("stroke", "currentColor");
  icon.setAttribute("stroke-width", "2");
  icon.setAttribute("stroke-linecap", "round");
  icon.setAttribute("stroke-linejoin", "round");
  for (const pathData of localIconPaths[iconName] ?? localIconPaths.default) {
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", pathData);
    icon.append(path);
  }
  return icon;
}

function replaceIconPlaceholders() {
  for (const placeholder of document.querySelectorAll(".material-symbols-outlined.button-icon")) {
    placeholder.replaceWith(createButtonIcon(placeholder.textContent.trim()));
  }
}

function setButtonLabel(button, iconName, label) {
  button.replaceChildren(createButtonIcon(iconName), document.createTextNode(label));
}

function requestConfirmation({ title, message, confirmLabel, confirmIcon = "check" }) {
  if (!elements.confirmationDialog || typeof elements.confirmationDialog.showModal !== "function") {
    return Promise.resolve(false);
  }
  if (elements.confirmationDialog.open || confirmationResolve) return Promise.resolve(false);

  elements.confirmationTitle.textContent = title;
  elements.confirmationMessage.textContent = message;
  setButtonLabel(elements.confirmationConfirm, confirmIcon, confirmLabel);
  confirmationReturnFocus = document.activeElement;
  elements.confirmationDialog.returnValue = "";
  elements.confirmationDialog.showModal();
  elements.confirmationConfirm.focus();

  return new Promise((resolve) => {
    confirmationResolve = resolve;
  });
}

function closeConfirmation(returnValue) {
  if (elements.confirmationDialog.open) elements.confirmationDialog.close(returnValue);
}

function finishConfirmation() {
  if (!confirmationResolve) return;
  const resolve = confirmationResolve;
  const returnFocus = confirmationReturnFocus;
  confirmationResolve = null;
  confirmationReturnFocus = null;
  resolve(elements.confirmationDialog.returnValue === "confirm");
  if (returnFocus instanceof HTMLElement && returnFocus.isConnected) {
    queueMicrotask(() => returnFocus.focus());
  }
}

function showLogin() {
  elements.loginScreen.hidden = false;
  elements.loginScreen.style.display = "grid";
  elements.appShell.hidden = true;
  elements.appShell.style.display = "none";
  elements.logoutButton.hidden = true;
  elements.loginForm.hidden = false;
  elements.bootstrapPanel.hidden = true;
}

function showApp() {
  elements.loginScreen.hidden = true;
  elements.loginScreen.style.display = "none";
  elements.appShell.hidden = false;
  elements.appShell.style.display = "block";
  elements.logoutButton.hidden = state.authConfig?.auth_mode !== "supabase";
}

async function fetchWithTimeout(url, options = {}, timeoutMilliseconds = 15_000) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMilliseconds);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("通信が時間内に完了しませんでした。FastAPIのターミナルを確認して再試行してください。");
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

async function api(path, options = {}) {
  const response = await fetchWithTimeout(`${apiBase}${path}`, {
    ...options,
    headers: {
      Accept: "application/json",
      ...(state.accessToken ? { Authorization: `Bearer ${state.accessToken}` } : {}),
      ...options.headers,
    },
  });
  if (response.ok) return response.status === 204 ? null : response.json();

  let message = "通信に失敗しました。";
  try {
    const body = await response.json();
    if (typeof body.detail === "string") message = body.detail;
  } catch {
    // A generic error is safer than showing an unexpected response body.
  }
  const error = new Error(message);
  error.status = response.status;
  throw error;
}

function formatDate(value) {
  return new Intl.DateTimeFormat("ja-JP", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function dateTimeLocalValue(value) {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "";
  const localTime = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return localTime.toISOString().slice(0, 16);
}

function categoryLabel(category) {
  return category === "injury" ? "怪我" : "成長記録";
}

function recordStatusLabel(status) {
  if (status === "approved") return "承認済み";
  if (status === "dispatched") return "配信済み";
  if (status === "rejected") return "却下";
  return "レビュー待ち";
}

function notificationStatusLabel(status) {
  if (status === "waiting_guardian_link") return "保護者LINEの連携待ち";
  if (status === "sent") return "送信済み";
  if (status === "failed") return "送信失敗";
  if (status === "cancelled") return "配信取消";
  return "送信待ち";
}

function notificationFailureMessage(kind) {
  if (kind === "guardian_not_linked") return "保護者のLINE連携を確認してください。";
  if (kind === "network") return "通信状況を確認して、再送を予約してください。";
  if (kind === "line_unavailable") return "LINE側の一時的な問題の可能性があります。時間を置いて再送してください。";
  if (kind === "line_rejected") return "LINE設定または保護者の連携状況を確認してください。";
  return "配信状況を確認して、必要に応じて再送してください。";
}

function audioJobStatusLabel(job) {
  if (job.status === "processing") return "GPU処理中";
  if (job.status === "completed") return job.record_id ? "記録作成済み" : "記録対象外";
  if (job.status === "failed") return "処理失敗";
  if (job.status === "expired") return "期限切れ";
  return "受付済み";
}

function audioJobDescription(job) {
  if (job.status === "processing") return "GPUワーカーが音声を解析しています。";
  if (job.status === "completed") {
    return job.record_id
      ? "レビュー待ちの記録を作成しました。"
      : "具体的な園児の出来事が確認できなかったため、記録は作成していません。";
  }
  if (job.status === "failed") return "音声は削除済みです。録音設定を確認して、もう一度送信してください。";
  if (job.status === "expired") return "時間内に処理されなかったため、音声を削除しました。";
  return "GPUワーカーの処理待ちです。";
}

function childName(childId) {
  return state.allChildren.find((child) => child.id === childId)?.display_name ?? "園児未選択";
}

function teacherName(teacherId) {
  return state.teachers.find((teacher) => teacher.id === teacherId)?.name ?? "担当先生未設定";
}

function selectedRecord() {
  return state.records.find((record) => record.id === state.selectedRecordId) ?? null;
}

function renderSchoolOptions(schools) {
  elements.schoolSelect.replaceChildren();
  for (const school of schools) {
    const option = document.createElement("option");
    option.value = school.id;
    option.textContent = school.name;
    elements.schoolSelect.append(option);
  }
  elements.schoolSelect.value = state.schoolId;
  elements.schoolSelect.disabled = schools.length < 2;
}

function selectedSchool() {
  return state.schools.find((school) => school.id === state.schoolId) ?? null;
}

function renderSchoolSettings() {
  const school = selectedSchool();
  if (!school) {
    elements.schoolDigestTimeInput.value = "";
    elements.schoolDigestTimeInput.disabled = true;
    elements.schoolDigestTimeSaveButton.disabled = true;
    elements.schoolTimezoneNote.textContent = "園を選択すると設定できます。";
    return;
  }
  elements.schoolDigestTimeInput.value = school.digest_time;
  elements.schoolDigestTimeInput.disabled = !state.isSchoolAdmin;
  elements.schoolDigestTimeSaveButton.disabled = !state.isSchoolAdmin;
  elements.schoolTimezoneNote.textContent = `園のタイムゾーン: ${school.timezone}`;
}

// ナビの「レビュー待ち」に添える件数。0 件のときはバッジを隠して、
// 先生の確認が必要な記録があるときだけ目に入るようにします。
function renderReviewNavCount() {
  const count = state.records.length;
  elements.reviewNavCount.textContent = `${count}件`;
  elements.reviewNavCount.hidden = count === 0;
}

function renderRecordList() {
  elements.recordCount.textContent = String(state.records.length);
  renderReviewNavCount();
  elements.recordList.replaceChildren();
  if (!state.records.length) {
    const text = document.createElement("p");
    text.className = "empty-list";
    text.textContent = "レビュー待ちの記録はありません。";
    elements.recordList.append(text);
    return;
  }

  for (const record of state.records) {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "record-item";
    const isSelected = record.id === state.selectedRecordId;
    item.classList.toggle("is-selected", isSelected);
    if (isSelected) item.setAttribute("aria-current", "true");
    item.dataset.recordId = record.id;

    const icon = createButtonIcon("description");
    const content = document.createElement("span");
    content.className = "record-item-content";
    const title = document.createElement("strong");
    title.textContent = `${childName(record.child_id)} / ${categoryLabel(record.category)}`;
    const detail = document.createElement("small");
    const lowConfidence = record.confidence < lowConfidenceThreshold;
    item.classList.toggle("is-low-confidence", lowConfidence);
    detail.textContent = `${formatDate(record.occurred_at)} - 信頼度 ${Math.round(record.confidence * 100)}%${lowConfidence ? " - 要確認" : ""}`;
    content.append(title, detail);
    item.append(icon, content);
    elements.recordList.append(item);
  }
}

function renderChildOptions(record) {
  elements.childSelect.replaceChildren();
  const emptyOption = document.createElement("option");
  emptyOption.value = "";
  emptyOption.textContent = "未選択";
  elements.childSelect.append(emptyOption);
  for (const child of state.children) {
    const option = document.createElement("option");
    option.value = child.id;
    option.textContent = child.display_name;
    elements.childSelect.append(option);
  }
  elements.childSelect.value = record.child_id ?? "";
}

function renderManualRecordOptions() {
  const selectedChildId = elements.manualRecordChildSelect.value;
  elements.manualRecordChildSelect.replaceChildren();
  for (const child of state.children) {
    const option = document.createElement("option");
    option.value = child.id;
    option.textContent = child.display_name;
    elements.manualRecordChildSelect.append(option);
  }
  elements.manualRecordChildSelect.value = state.children.some((child) => child.id === selectedChildId)
    ? selectedChildId
    : (state.children[0]?.id ?? "");

  const isDevelopment = state.authConfig?.auth_mode === "development";
  elements.manualRecordTeacherField.hidden = !isDevelopment;
  if (!isDevelopment) return;
  const selectedTeacherId = elements.manualRecordTeacherSelect.value;
  const activeTeachers = state.teachers.filter((teacher) => teacher.is_active);
  elements.manualRecordTeacherSelect.replaceChildren();
  for (const teacher of activeTeachers) {
    const option = document.createElement("option");
    option.value = teacher.id;
    option.textContent = teacher.name;
    elements.manualRecordTeacherSelect.append(option);
  }
  elements.manualRecordTeacherSelect.value = activeTeachers.some((teacher) => teacher.id === selectedTeacherId)
    ? selectedTeacherId
    : (activeTeachers[0]?.id ?? "");
}

function renderDetail() {
  const record = selectedRecord();
  elements.emptyState.hidden = Boolean(record) || state.manualRecordMode;
  elements.reviewForm.hidden = !record || state.manualRecordMode;
  elements.manualRecordForm.hidden = !state.manualRecordMode;
  elements.manualRecordOpenButton.disabled = !state.children.length;
  if (state.manualRecordMode) {
    renderManualRecordOptions();
    return;
  }
  if (!record) {
    elements.summaryInput.value = "";
    elements.promptInput.value = "";
    elements.scheduledForEnabled.checked = false;
    elements.scheduledForInput.value = "";
    elements.scheduledForInput.disabled = true;
    elements.recordConfidenceWarning.hidden = true;
    updateReviewCharacterCounts();
    return;
  }
  const lowConfidence = record.confidence < lowConfidenceThreshold;
  elements.recordMeta.textContent = `${formatDate(record.occurred_at)} / 信頼度 ${Math.round(record.confidence * 100)}%`;
  elements.recordConfidenceWarning.hidden = !lowConfidence;
  elements.recordCategory.textContent = categoryLabel(record.category);
  elements.summaryInput.value = record.summary;
  elements.promptInput.value = record.conversation_prompt ?? "";
  elements.scheduledForEnabled.checked = false;
  elements.scheduledForInput.value = "";
  elements.scheduledForInput.disabled = true;
  updateReviewCharacterCounts();
  renderChildOptions(record);
}

function renderHome() {
  elements.homeReviewCount.textContent = String(state.records.length);
  elements.homePendingCount.textContent = String(state.notifications.filter((item) => item.status === "pending").length);
  elements.homeSentCount.textContent = String(state.notifications.filter((item) => item.status === "sent").length);
  elements.homeWaitingGuardianLinkCount.textContent = String(
    state.notifications.filter((item) => item.status === "waiting_guardian_link").length,
  );
}

// ナビの「園児・保護者」に添える、招待コードがまだ出ていない園児の件数。
// 配信はここが埋まるまで始まらないので、在籍中の園児だけを数えます。
// 発行できるのは管理者だけ（サーバー側も assert_school_admin）なので、
// 一般の先生には出しません。
// 「3件」だけでは何の件数か分からないため、読み上げ用に aria-label を添えます。
function renderChildInvitationNavCount() {
  const count = state.isSchoolAdmin
    ? state.children.filter(
      (child) => !child.guardian_line_user_id
        && !state.lineLinkInvitations.some((invitation) => invitation.child_id === child.id),
    ).length
    : 0;
  elements.childInvitationNavCount.textContent = `${count}件`;
  elements.childInvitationNavCount.setAttribute("aria-label", `招待コード未発行${count}件`);
  elements.childInvitationNavCount.hidden = count === 0;
}

function renderChildManagement() {
  renderChildInvitationNavCount();
  elements.childCount.textContent = String(state.children.length);
  elements.childForm.hidden = !state.isSchoolAdmin;
  elements.childRoleNote.hidden = state.isSchoolAdmin;
  elements.childList.replaceChildren();

  if (!state.allChildren.length) {
    const text = document.createElement("p");
    text.className = "empty-list";
    text.textContent = "園児はまだ登録されていません。";
    elements.childList.append(text);
    return;
  }

  for (const child of state.allChildren) {
    const item = document.createElement("article");
    item.className = "child-item";

    const content = document.createElement("div");
    const name = document.createElement("h3");
    name.textContent = child.display_name;
    const statuses = document.createElement("div");
    statuses.className = "child-statuses";
    const enrollmentStatus = document.createElement("span");
    enrollmentStatus.className = `child-status ${child.is_active ? "is-active" : "is-archived"}`;
    enrollmentStatus.textContent = child.is_active ? "在籍中" : "退園済み";
    statuses.append(enrollmentStatus);
    if (child.is_active) {
      const guardianStatus = document.createElement("span");
      guardianStatus.className = "guardian-status";
      guardianStatus.classList.toggle("is-linked", Boolean(child.guardian_line_user_id));
      guardianStatus.textContent = child.guardian_line_user_id ? "LINE連携済み" : "LINE未連携";
      statuses.append(guardianStatus);
      const invitation = state.lineLinkInvitations.find((item) => item.child_id === child.id);
      if (invitation) {
        const invitationStatus = document.createElement("span");
        invitationStatus.className = "guardian-status is-invitation-pending";
        invitationStatus.textContent = `招待済み: ${formatDate(invitation.expires_at)}まで`;
        statuses.append(invitationStatus);
      }
      content.append(name, statuses);
    } else if (child.archived_at) {
      const archiveDate = document.createElement("p");
      archiveDate.className = "child-meta";
      archiveDate.textContent = `退園処理: ${formatDate(child.archived_at)}`;
      content.append(name, statuses, archiveDate);
    } else {
      content.append(name, statuses);
    }
    item.append(content);

    const actions = document.createElement("div");
    actions.className = "child-actions";
    if (state.isSchoolAdmin && child.is_active && !child.guardian_line_user_id) {
      const invitation = state.lineLinkInvitations.find((item) => item.child_id === child.id);
      const inviteButton = document.createElement("button");
      inviteButton.type = "button";
      inviteButton.className = "child-invite-button";
      inviteButton.dataset.childAction = "line-invite";
      inviteButton.dataset.childId = child.id;
      setButtonLabel(inviteButton, "person_add", invitation ? "新しいコードを発行" : "招待コードを発行");
      actions.append(inviteButton);
    }
    if (state.isSchoolAdmin && child.is_active && child.guardian_line_user_id) {
      const archiveButton = document.createElement("button");
      archiveButton.type = "button";
      archiveButton.className = "child-archive-button";
      archiveButton.dataset.childAction = "guardian-archive";
      archiveButton.dataset.childId = child.id;
      setButtonLabel(archiveButton, "link", "配信アーカイブURLを発行");
      actions.append(archiveButton);

      const unlinkButton = document.createElement("button");
      unlinkButton.type = "button";
      unlinkButton.className = "child-unlink-button";
      unlinkButton.dataset.childAction = "guardian-unlink";
      unlinkButton.dataset.childId = child.id;
      setButtonLabel(unlinkButton, "link_off", "LINE連携を解除");
      actions.append(unlinkButton);
    }
    if (state.isSchoolAdmin && child.is_active) {
      const editButton = document.createElement("button");
      editButton.type = "button";
      editButton.className = "child-edit-button";
      editButton.dataset.childAction = "edit";
      editButton.dataset.childId = child.id;
      setButtonLabel(editButton, "edit", "名前を編集");
      actions.append(editButton);

      const retireButton = document.createElement("button");
      retireButton.type = "button";
      retireButton.className = "child-retire-button";
      retireButton.dataset.childAction = "archive";
      retireButton.dataset.childId = child.id;
      setButtonLabel(retireButton, "person_remove", "退園処理");
      actions.append(retireButton);
    }
    if (state.isSchoolAdmin && !child.is_active) {
      const restoreButton = document.createElement("button");
      restoreButton.type = "button";
      restoreButton.className = "child-restore-button";
      restoreButton.dataset.childAction = "restore";
      restoreButton.dataset.childId = child.id;
      setButtonLabel(restoreButton, "refresh", "復園に戻す");
      actions.append(restoreButton);
    }
    if (actions.childNodes.length) {
      item.append(actions);
    }
    if (state.isSchoolAdmin && child.is_active && state.editingChildId === child.id) {
      item.append(createChildEditForm(child));
    }
    elements.childList.append(item);
  }
}

function createChildEditForm(child) {
  const form = document.createElement("form");
  form.className = "child-edit-form";
  form.dataset.childEditForm = child.id;
  const label = document.createElement("label");
  label.textContent = "園児の表示名";
  const input = document.createElement("input");
  input.name = "display_name";
  input.type = "text";
  input.required = true;
  input.maxLength = 120;
  input.value = child.display_name;
  label.append(input);
  const actions = document.createElement("div");
  actions.className = "child-edit-actions";
  const saveButton = document.createElement("button");
  saveButton.className = "button-primary";
  saveButton.type = "submit";
  setButtonLabel(saveButton, "check", "保存");
  const closeButton = document.createElement("button");
  closeButton.className = "button-tertiary";
  closeButton.type = "button";
  closeButton.dataset.childAction = "edit-close";
  setButtonLabel(closeButton, "close", "閉じる");
  actions.append(saveButton, closeButton);
  form.append(label, actions);
  return form;
}

function renderHistoryChildOptions() {
  const selectedValue = elements.recordHistoryChildSelect.value;
  elements.recordHistoryChildSelect.replaceChildren();
  const allOption = document.createElement("option");
  allOption.value = "";
  allOption.textContent = "すべて";
  elements.recordHistoryChildSelect.append(allOption);
  for (const child of state.allChildren) {
    const option = document.createElement("option");
    option.value = child.id;
    option.textContent = child.is_active ? child.display_name : `${child.display_name}（退園済み）`;
    elements.recordHistoryChildSelect.append(option);
  }
  elements.recordHistoryChildSelect.value = selectedValue;
}

function renderRecordHistory() {
  renderHistoryChildOptions();
  elements.recordHistoryCount.textContent = String(state.historyRecords.length);
  elements.recordHistoryExportButton.hidden = !state.isSchoolAdmin;
  elements.recordHistoryExportButton.disabled = !state.isSchoolAdmin || !state.historyRecords.length;
  elements.recordHistoryList.replaceChildren();
  if (!state.historyRecords.length) {
    const text = document.createElement("p");
    text.className = "empty-list";
    text.textContent = "条件に合う記録はありません。";
    elements.recordHistoryList.append(text);
    return;
  }

  for (const record of state.historyRecords) {
    const item = document.createElement("article");
    item.className = "record-history-item";
    const content = document.createElement("div");
    const title = document.createElement("h3");
    title.textContent = `${childName(record.child_id)} / ${categoryLabel(record.category)}`;
    const meta = document.createElement("p");
    meta.className = "record-history-meta";
    meta.textContent = `発生: ${formatDate(record.occurred_at)}${record.reviewed_at ? ` / 確認: ${formatDate(record.reviewed_at)}` : ""}`;
    const summary = document.createElement("p");
    summary.className = "record-history-summary";
    summary.textContent = record.summary;
    content.append(title, meta, summary);
    if (record.conversation_prompt) {
      const prompt = document.createElement("p");
      prompt.className = "record-history-prompt";
      prompt.textContent = `会話のきっかけ: ${record.conversation_prompt}`;
      content.append(prompt);
    }
    const status = document.createElement("span");
    status.className = `record-history-status is-${record.status}`;
    status.textContent = recordStatusLabel(record.status);
    item.append(content, status);
    elements.recordHistoryList.append(item);
  }
}

function teacherRoleLabel(role) {
  return role === "school_admin" ? "先生管理者" : "先生";
}

function renderTeacherManagement() {
  elements.teacherCount.textContent = String(state.teachers.length);
  elements.teacherList.replaceChildren();

  if (!state.teachers.length) {
    const text = document.createElement("p");
    text.className = "empty-list";
    text.textContent = "登録済みの先生はいません。";
    elements.teacherList.append(text);
    return;
  }

  for (const teacher of state.teachers) {
    const item = document.createElement("article");
    item.className = "teacher-item";

    const identity = document.createElement("div");
    const name = document.createElement("h3");
    name.textContent = teacher.name;
    const email = document.createElement("p");
    email.textContent = teacher.email ?? "メールアドレス未設定";
    identity.append(name, email);

    const status = document.createElement("div");
    status.className = "teacher-statuses";
    const role = document.createElement("span");
    role.className = "teacher-role";
    role.textContent = teacherRoleLabel(teacher.role);
    const account = document.createElement("span");
    account.className = `teacher-account-status ${teacher.is_active ? "is-active" : "is-disabled"}`;
    account.textContent = teacher.is_active ? "利用中" : "利用停止";
    const auth = document.createElement("span");
    auth.className = "teacher-auth-status";
    auth.classList.toggle("is-linked", teacher.is_auth_linked);
    auth.textContent = teacher.is_auth_linked ? "ログイン設定済み" : "招待待ち";
    status.append(role, account, auth);

    const controls = document.createElement("div");
    controls.className = "teacher-controls";
    controls.append(status);
    if (state.isSchoolAdmin && teacher.is_active && teacher.id !== state.currentTeacherId) {
      const roleButton = document.createElement("button");
      roleButton.type = "button";
      roleButton.className = "teacher-role-button";
      roleButton.dataset.teacherAction = teacher.role === "school_admin" ? "demote" : "promote";
      roleButton.dataset.teacherId = teacher.id;
      if (teacher.role === "school_admin") {
        setButtonLabel(roleButton, "group", "先生に戻す");
      } else {
        setButtonLabel(roleButton, "admin_panel_settings", "管理者にする");
      }
      controls.append(roleButton);

      const disableButton = document.createElement("button");
      disableButton.type = "button";
      disableButton.className = "teacher-disable-button";
      disableButton.dataset.teacherAction = "disable";
      disableButton.dataset.teacherId = teacher.id;
      setButtonLabel(disableButton, "block", "利用停止");
      controls.append(disableButton);
    }
    if (state.isSchoolAdmin && !teacher.is_active) {
      const restoreButton = document.createElement("button");
      restoreButton.type = "button";
      restoreButton.className = "teacher-restore-button";
      restoreButton.dataset.teacherAction = "restore";
      restoreButton.dataset.teacherId = teacher.id;
      setButtonLabel(restoreButton, "refresh", "利用を再開");
      controls.append(restoreButton);
    }

    item.append(identity, controls);
    elements.teacherList.append(item);
  }
  renderEdgeDeviceManagement();
}

function renderEdgeDeviceTeacherOptions() {
  elements.edgeDeviceTeacherSelect.replaceChildren();
  const activeTeachers = state.teachers.filter((teacher) => teacher.is_active);
  for (const teacher of activeTeachers) {
    const option = document.createElement("option");
    option.value = teacher.id;
    option.textContent = teacher.name;
    elements.edgeDeviceTeacherSelect.append(option);
  }
  elements.edgeDeviceTeacherSelect.disabled = !activeTeachers.length;
  elements.edgeDeviceCreateButton.disabled = !activeTeachers.length;
}

function edgeDeviceConnectionStatus(device) {
  if (!device.is_active) return { label: "無効", className: "is-disabled" };
  if (!device.last_seen_at) return { label: "未接続", className: "is-unseen" };

  const lastSeenMilliseconds = Date.parse(device.last_seen_at);
  if (Number.isFinite(lastSeenMilliseconds) && Date.now() - lastSeenMilliseconds <= 3 * 60 * 1000) {
    return { label: "接続中", className: "is-online" };
  }
  return { label: "応答待ち", className: "is-stale" };
}

function renderEdgeDeviceManagement() {
  elements.edgeDeviceForm.hidden = !state.isSchoolAdmin;
  elements.edgeDeviceCount.textContent = String(state.edgeDevices.length);
  renderEdgeDeviceTeacherOptions();
  elements.edgeDeviceList.replaceChildren();

  if (!state.edgeDevices.length) {
    const text = document.createElement("p");
    text.className = "empty-list";
    text.textContent = "登録済みの録音端末はありません。";
    elements.edgeDeviceList.append(text);
    return;
  }

  for (const device of state.edgeDevices) {
    const item = document.createElement("article");
    item.className = "edge-device-item";

    const identity = document.createElement("div");
    const name = document.createElement("h3");
    name.textContent = device.name;
    const owner = document.createElement("p");
    owner.textContent = `担当: ${teacherName(device.teacher_id)}`;
    const lastSeen = document.createElement("p");
    lastSeen.className = "edge-device-meta";
    lastSeen.textContent = device.last_seen_at
      ? `最終通信: ${formatDate(device.last_seen_at)}`
      : "最終通信: まだありません";
    identity.append(name, owner, lastSeen);

    const controls = document.createElement("div");
    controls.className = "edge-device-controls";
    const status = document.createElement("span");
    status.className = "edge-device-status";
    status.classList.toggle("is-active", device.is_active);
    status.textContent = device.is_active ? "端末有効" : "端末無効";
    const connection = document.createElement("span");
    const connectionStatus = edgeDeviceConnectionStatus(device);
    connection.className = `edge-device-connection ${connectionStatus.className}`;
    connection.textContent = connectionStatus.label;
    controls.append(status, connection);

    const rotateButton = document.createElement("button");
    rotateButton.type = "button";
    rotateButton.className = "edge-device-action";
    rotateButton.dataset.edgeDeviceAction = "rotate";
    rotateButton.dataset.edgeDeviceId = device.id;
    setButtonLabel(rotateButton, "key", device.is_active ? "鍵を再発行" : "鍵を再発行して有効化");
    controls.append(rotateButton);

    if (device.is_active) {
      const disableButton = document.createElement("button");
      disableButton.type = "button";
      disableButton.className = "edge-device-disable";
      disableButton.dataset.edgeDeviceAction = "disable";
      disableButton.dataset.edgeDeviceId = device.id;
      setButtonLabel(disableButton, "block", "端末を無効化");
      controls.append(disableButton);
    }

    item.append(identity, controls);
    elements.edgeDeviceList.append(item);
  }
}

function auditEventActionLabel(action) {
  const labels = {
    line_link_invitation_issued: "保護者LINEの招待コードを発行",
    guardian_line_linked: "保護者LINEが連携済みになりました",
    guardian_line_unlinked: "保護者LINEの連携を解除",
    guardian_archive_issued: "配信アーカイブURLを発行",
    guardian_archive_revoked: "配信アーカイブURLを無効化",
    record_approved: "記録を承認",
    record_rejected: "記録を却下",
    notification_retry_scheduled: "LINE通知の再送を予約",
    notification_cancelled: "LINE通知を取消",
    notification_rescheduled: "LINE通知の配信日時を変更",
    child_updated: "園児の表示名を変更",
    child_archived: "園児を退園処理",
    child_restored: "園児を復園へ戻す",
    teacher_disabled: "先生アカウントを利用停止",
    teacher_restored: "先生アカウントの利用を再開",
    teacher_role_changed: "先生の権限を変更",
    school_digest_time_changed: "成長記録の配信時刻を変更",
    manual_record_created: "手入力の記録を作成",
    record_history_exported: "記録履歴をCSV出力",
    audit_history_exported: "操作履歴をCSV出力",
    notion_synced: "Notionに記録",
    edge_device_created: "録音端末を登録",
    edge_device_key_rotated: "録音端末のキーを再発行",
    edge_device_disabled: "録音端末を無効化",
  };
  return labels[action] ?? "運用操作を実行";
}

function renderAuditEventManagement() {
  elements.auditEventCount.textContent = String(state.auditEvents.length);
  elements.auditEventsExportButton.hidden = !state.isSchoolAdmin;
  elements.auditEventsExportButton.disabled = !state.isSchoolAdmin || !state.auditEvents.length;
  elements.auditEventList.replaceChildren();

  if (!state.auditEvents.length) {
    const text = document.createElement("p");
    text.className = "empty-list";
    text.textContent = "操作履歴はまだありません。";
    elements.auditEventList.append(text);
    return;
  }

  for (const event of state.auditEvents) {
    const item = document.createElement("article");
    item.className = "audit-event-item";
    const content = document.createElement("div");
    const action = document.createElement("h3");
    action.textContent = auditEventActionLabel(event.action);
    const meta = document.createElement("p");
    meta.className = "audit-event-meta";
    meta.textContent = `${formatDate(event.created_at)} / ${event.actor_display_name ?? "システム"}`;
    content.append(action, meta);
    item.append(content);
    elements.auditEventList.append(item);
  }
}

function setRuntimeCheck(statusElement, noteElement, { label, note, tone }) {
  statusElement.textContent = label;
  statusElement.className = `runtime-check-status is-${tone}`;
  noteElement.textContent = note;
}

function renderRuntimeReadiness() {
  if (!state.isSchoolAdmin) return;

  const readiness = state.runtimeReadiness;
  if (!readiness) {
    elements.runtimeOverallStatus.textContent = "未確認";
    elements.runtimeOverallStatus.className = "runtime-overall-status";
    return;
  }

  const isReady = readiness.status === "ready";
  elements.runtimeOverallStatus.textContent = isReady ? "基本準備は完了" : "確認が必要";
  elements.runtimeOverallStatus.className = `runtime-overall-status is-${isReady ? "ready" : "attention"}`;
  setRuntimeCheck(elements.runtimeDatabaseStatus, elements.runtimeDatabaseNote, readiness.database_ready
    ? { label: "確認済み", note: "データベースに接続できます。", tone: "ready" }
    : { label: "接続を確認", note: "データベースの設定と起動状態を確認してください。", tone: "attention" });
  setRuntimeCheck(elements.runtimeMigrationStatus, elements.runtimeMigrationNote, readiness.database_migration_current
    ? { label: "最新です", note: "必要なデータベース更新が適用されています。", tone: "ready" }
    : { label: "更新が必要", note: "VRTへ切り替える前にデータベース更新を実行してください。", tone: "attention" });

  if (!readiness.cloud_audio_enabled) {
    setRuntimeCheck(elements.runtimeAudioModeStatus, elements.runtimeAudioModeNote, {
      label: "Macでローカル処理中",
      note: "VRTはまだ使っていません。現在の開発・テストはこのまま続けられます。",
      tone: "local",
    });
    setRuntimeCheck(elements.runtimeStorageStatus, elements.runtimeStorageNote, {
      label: "VRT切替時に確認",
      note: "VRTでクラウド音声処理を有効にした後に、一時保存先を確認します。",
      tone: "local",
    });
    setRuntimeCheck(elements.runtimeLlmStatus, elements.runtimeLlmNote, {
      label: "VRT切替時に確認",
      note: "VRTでクラウド音声処理を有効にした後に、文章生成AIを確認します。",
      tone: "local",
    });
    setRuntimeCheck(elements.runtimeGpuWorkerStatus, elements.runtimeGpuWorkerNote, {
      label: "VRT切替時に確認",
      note: "VRTでクラウド音声処理を有効にした後に、GPUワーカーの稼働を確認します。",
      tone: "local",
    });
  } else {
    setRuntimeCheck(elements.runtimeAudioModeStatus, elements.runtimeAudioModeNote, {
      label: "VRTでクラウド処理中",
      note: "録音端末からの音声はVRTで短時間だけ処理します。",
      tone: "ready",
    });
    setRuntimeCheck(elements.runtimeStorageStatus, elements.runtimeStorageNote, readiness.cloud_audio_job_storage_ready
      ? { label: "確認済み", note: "VRT上の一時音声保存先を利用できます。", tone: "ready" }
      : { label: "設定を確認", note: "VRT上の一時音声保存先を確認してください。", tone: "attention" });
    setRuntimeCheck(elements.runtimeLlmStatus, elements.runtimeLlmNote, readiness.cloud_audio_llm_configured
      ? { label: "確認済み", note: "VRT上の文章生成AIの設定を確認できました。", tone: "ready" }
      : { label: "設定を確認", note: "VRT上の文章生成AIの設定を確認してください。", tone: "attention" });
    setRuntimeCheck(elements.runtimeGpuWorkerStatus, elements.runtimeGpuWorkerNote, readiness.cloud_audio_worker_ready
      ? { label: "稼働中", note: "GPU音声処理ワーカーから定期的な稼働確認を受け取っています。", tone: "ready" }
      : { label: "停止を確認", note: "GPUワーカーの起動状態とログを確認してください。", tone: "attention" });
  }

  setRuntimeCheck(elements.runtimeLineStatus, elements.runtimeLineNote, readiness.line_delivery_configured
    ? { label: "確認済み", note: "LINE配信に必要な設定が入っています。", tone: "ready" }
    : { label: "設定を確認", note: "LINEの通知を配信する前に設定を確認してください。", tone: "attention" });
  if (!readiness.line_delivery_configured) {
    setRuntimeCheck(elements.runtimeLineWorkerStatus, elements.runtimeLineWorkerNote, {
      label: "設定後に確認",
      note: "LINE配信設定を入れた後に、送信ワーカーの稼働を確認します。",
      tone: "local",
    });
  } else {
    setRuntimeCheck(elements.runtimeLineWorkerStatus, elements.runtimeLineWorkerNote, readiness.line_delivery_worker_ready
      ? { label: "稼働中", note: "LINE送信ワーカーから定期的な稼働確認を受け取っています。", tone: "ready" }
      : { label: "停止を確認", note: "LINE送信ワーカーの起動状態とログを確認してください。", tone: "attention" });
  }
}

function renderVoiceConsent() {
  if (state.authConfig?.auth_mode === "development") {
    elements.voiceConsentStatus.textContent = "声紋設定は、Supabaseでログインした先生アカウントでのみ変更できます。";
    elements.voiceConsentStatus.className = "voice-consent-status is-inactive";
    elements.voiceConsentForm.hidden = true;
    return;
  }

  elements.voiceConsentForm.hidden = false;
  const consent = state.voiceConsent;
  if (!consent) {
    elements.voiceConsentStatus.textContent = "声紋登録への同意はまだ保存されていません。";
    elements.voiceConsentStatus.className = "voice-consent-status";
    elements.voiceConsentRevokeButton.hidden = true;
    elements.voiceConsentSubmitButton.disabled = false;
    setButtonLabel(elements.voiceConsentSubmitButton, "check", "同意を保存");
    return;
  }

  elements.voiceConsentRetentionDays.value = consent.retention_days;
  if (consent.is_active) {
    elements.voiceConsentStatus.textContent = `同意済みです。有効期限: ${formatDate(consent.expires_at)}`;
    elements.voiceConsentStatus.className = "voice-consent-status is-active";
    elements.voiceConsentRevokeButton.hidden = false;
    setButtonLabel(elements.voiceConsentSubmitButton, "refresh", "同意を更新");
    return;
  }

  elements.voiceConsentStatus.textContent = consent.revoked_at
    ? "同意は取り消されています。再開するには、もう一度同意を保存してください。"
    : "同意の有効期限が切れています。再開するには、もう一度同意を保存してください。";
  elements.voiceConsentStatus.className = "voice-consent-status is-inactive";
  elements.voiceConsentRevokeButton.hidden = true;
  setButtonLabel(elements.voiceConsentSubmitButton, "check", "同意を更新");
}

function render() {
  applySchoolAdminVisibility();
  renderRecordList();
  renderDetail();
  renderHome();
  renderChildManagement();
  renderRecordHistory();
  renderTeacherManagement();
  renderEdgeDeviceManagement();
  renderRuntimeReadiness();
  renderAuditEventManagement();
  renderVoiceConsent();
}

// ナビの「通知状況」に添える送信失敗の件数。すぐ手当てが必要なものなので、
// 一覧の絞り込み結果ではなく園全体の件数を出し、0 件のときは隠します。
// 見た目は「！3件」と短くしますが、それだけでは何の件数か分からないので、
// 読み上げ用に aria-label で「送信失敗3件」と補います。
function renderNotificationNavCount() {
  const count = state.notifications.filter((item) => item.status === "failed").length;
  elements.notificationNavCount.textContent = `！${count}件`;
  elements.notificationNavCount.setAttribute("aria-label", `送信失敗${count}件`);
  elements.notificationNavCount.hidden = count === 0;
}

function renderNotifications() {
  renderNotificationNavCount();
  const statusFilter = elements.notificationStatusSelect.value;
  const search = elements.notificationSearch.value.trim().toLocaleLowerCase("ja-JP");
  const notifications = state.notifications.filter((notification) => {
    if (statusFilter && notification.status !== statusFilter) return false;
    if (!search) return true;
    const searchable = [
      notification.child_display_name ?? "園児未選択",
      notification.summary,
      categoryLabel(notification.category),
      notificationStatusLabel(notification.status),
    ].join(" ").toLocaleLowerCase("ja-JP");
    return searchable.includes(search);
  });
  elements.notificationCount.textContent = String(notifications.length);
  elements.notificationList.replaceChildren();
  renderHome();
  if (!notifications.length) {
    const text = document.createElement("p");
    text.className = "empty-list";
    text.textContent = state.notifications.length
      ? "条件に合う通知はありません。"
      : "通知はまだありません。";
    elements.notificationList.append(text);
    return;
  }

  for (const notification of notifications) {
    const item = document.createElement("article");
    item.className = "notification-item";
    const content = document.createElement("div");
    const title = document.createElement("h3");
    title.textContent = `${notification.child_display_name ?? "園児未選択"} / ${categoryLabel(notification.category)}`;
    const summary = document.createElement("p");
    summary.className = "notification-summary";
    summary.textContent = notification.summary;
    content.append(title, summary);

    const status = document.createElement("span");
    status.className = "delivery-status";
    status.classList.toggle("is-sent", notification.status === "sent");
    status.classList.toggle("is-waiting-guardian-link", notification.status === "waiting_guardian_link");
    status.classList.toggle("is-failed", notification.status === "failed");
    status.classList.toggle("is-cancelled", notification.status === "cancelled");
    status.textContent = notificationStatusLabel(notification.status);
    const meta = document.createElement("p");
    meta.className = "notification-meta";
    const deliveryMeta = notification.status === "waiting_guardian_link"
      ? `配信予定: ${formatDate(notification.scheduled_for)} / 保護者LINEを連携すると送信待ちになります`
      : notification.status === "cancelled"
      ? "送信前に取消済み"
      : notification.sent_at
        ? `送信: ${formatDate(notification.sent_at)}`
        : `配信予定: ${formatDate(notification.scheduled_for)}`;
    const attemptMeta = notification.delivery_attempts > 0
      ? ` / 送信試行: ${notification.delivery_attempts}回`
      : "";
    const failureMeta = notification.status === "failed"
      ? ` / ${notificationFailureMessage(notification.last_failure_kind)}`
      : "";
    meta.textContent = `${deliveryMeta}${attemptMeta}${failureMeta}`;

    const notificationActions = document.createElement("div");
    notificationActions.className = "notification-actions";
    if (state.isSchoolAdmin && notification.status === "waiting_guardian_link" && notification.child_id) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "notification-guardian-link-button";
      button.dataset.notificationGuardianLinkChildId = notification.child_id;
      setButtonLabel(button, "link", "園児・保護者を開く");
      notificationActions.append(button);
    }
    if (state.isSchoolAdmin && notification.notion_synced_at) {
      const synced = document.createElement("span");
      synced.className = "notification-notion-status";
      synced.textContent = `Notionに記録済み: ${formatDate(notification.notion_synced_at)}`;
      notificationActions.append(synced);
      if (notification.notion_page_url) {
        const link = document.createElement("a");
        link.className = "notification-notion-link";
        link.href = notification.notion_page_url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = "Notionで開く";
        notificationActions.append(link);
      }
    } else if (state.isSchoolAdmin && notification.status === "sent") {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "notification-notion-button";
      button.dataset.notionSyncRecordId = notification.record_id;
      setButtonLabel(button, "description", "Notionに記録");
      notificationActions.append(button);
    }

    if (state.isSchoolAdmin && notification.status === "failed") {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "notification-retry-button";
      button.dataset.notificationRetryId = notification.id;
      setButtonLabel(button, "refresh", "再送を予約");
      notificationActions.append(button);
    }

    const isQueuedForDelivery = ["pending", "waiting_guardian_link"].includes(notification.status);
    if (state.isSchoolAdmin && isQueuedForDelivery) {
      const rescheduleButton = document.createElement("button");
      rescheduleButton.type = "button";
      rescheduleButton.className = "notification-reschedule-button";
      rescheduleButton.dataset.notificationRescheduleId = notification.id;
      setButtonLabel(rescheduleButton, "schedule", "日時を変更");
      notificationActions.append(rescheduleButton);

      const button = document.createElement("button");
      button.type = "button";
      button.className = "notification-cancel-button";
      button.dataset.notificationCancelId = notification.id;
      setButtonLabel(button, "block", "配信を取消");
      notificationActions.append(button);
    }

    item.append(content, status, meta);
    if (notificationActions.childElementCount) item.append(notificationActions);
    if (state.reschedulingNotificationId === notification.id && isQueuedForDelivery) {
      item.append(createNotificationRescheduleForm(notification));
    }
    elements.notificationList.append(item);
  }
}

function createNotificationRescheduleForm(notification) {
  const form = document.createElement("form");
  form.className = "notification-reschedule-form";
  form.dataset.notificationRescheduleForm = notification.id;

  const label = document.createElement("label");
  const inputId = `notification-schedule-${notification.id}`;
  label.htmlFor = inputId;
  label.textContent = "新しい配信日時";

  const input = document.createElement("input");
  input.id = inputId;
  input.name = "scheduled_for";
  input.type = "datetime-local";
  input.required = true;
  input.value = dateTimeLocalValue(notification.scheduled_for);
  input.min = dateTimeLocalValue(new Date(Date.now() + 60_000));
  label.append(input);

  const support = document.createElement("p");
  support.className = "field-support";
  support.textContent = notification.status === "waiting_guardian_link"
    ? "未来の日時を指定してください。保護者がLINE連携した後も、この日時まで送信されません。"
    : "未来の日時を指定してください。LINE送信が始まる前だけ変更できます。";

  const actions = document.createElement("div");
  actions.className = "notification-reschedule-actions";
  const saveButton = document.createElement("button");
  saveButton.type = "submit";
  saveButton.className = "notification-reschedule-save";
  setButtonLabel(saveButton, "schedule", "この日時で予約");
  const closeButton = document.createElement("button");
  closeButton.type = "button";
  closeButton.className = "notification-reschedule-close";
  closeButton.dataset.notificationRescheduleCloseId = notification.id;
  setButtonLabel(closeButton, "close", "変更をやめる");
  actions.append(saveButton, closeButton);
  form.append(label, support, actions);
  return form;
}

function renderAudioJobs() {
  elements.audioJobCount.textContent = String(state.audioJobs.length);
  elements.audioJobList.replaceChildren();
  if (!state.audioJobs.length) {
    const text = document.createElement("p");
    text.className = "empty-list";
    text.textContent = "音声処理の履歴はまだありません。";
    elements.audioJobList.append(text);
    return;
  }

  for (const job of state.audioJobs) {
    const item = document.createElement("article");
    item.className = "audio-job-item";

    const content = document.createElement("div");
    const title = document.createElement("h3");
    title.textContent = "音声処理ジョブ";
    const meta = document.createElement("p");
    meta.className = "audio-job-meta";
    meta.textContent = `受付: ${formatDate(job.queued_at)} / 処理試行: ${job.attempts}回`;
    const description = document.createElement("p");
    description.className = "audio-job-description";
    description.textContent = audioJobDescription(job);
    content.append(title, meta, description);

    const status = document.createElement("span");
    status.className = `audio-job-status is-${job.status}`;
    status.textContent = audioJobStatusLabel(job);
    item.append(content, status);
    elements.audioJobList.append(item);
  }
}

async function loadRecords() {
  const params = new URLSearchParams({ school_id: state.schoolId, record_status: "pending_review" });
  const [allChildren, records] = await Promise.all([
    api(`/children?school_id=${encodeURIComponent(state.schoolId)}&include_archived=true`),
    api(`/records?${params}`),
  ]);
  state.allChildren = allChildren;
  state.children = allChildren.filter((child) => child.is_active);
  state.records = records;
  if (!state.records.some((record) => record.id === state.selectedRecordId)) {
    state.selectedRecordId = state.records[0]?.id ?? null;
  }
  render();
}

async function loadActiveLineLinkInvitations() {
  if (!state.isSchoolAdmin) {
    state.lineLinkInvitations = [];
    renderChildManagement();
    return;
  }
  state.lineLinkInvitations = await api(
    `/line/link-invitations/active?school_id=${encodeURIComponent(state.schoolId)}`,
  );
  renderChildManagement();
}

function dateFilterToIso(value, isEndOfDay = false) {
  if (!value) return null;
  const date = new Date(`${value}T${isEndOfDay ? "23:59:59.999" : "00:00:00.000"}`);
  return Number.isFinite(date.getTime()) ? date.toISOString() : null;
}

function recordHistoryParams() {
  const params = new URLSearchParams({ school_id: state.schoolId, limit: "100" });
  const search = elements.recordHistorySearch.value.trim();
  const childId = elements.recordHistoryChildSelect.value;
  const recordStatus = elements.recordHistoryStatusSelect.value;
  const category = elements.recordHistoryCategorySelect.value;
  const occurredFrom = dateFilterToIso(elements.recordHistoryFrom.value);
  const occurredTo = dateFilterToIso(elements.recordHistoryTo.value, true);
  if (search) params.set("search", search);
  if (childId) params.set("child_id", childId);
  if (recordStatus) params.set("record_status", recordStatus);
  if (category) params.set("category", category);
  if (occurredFrom) params.set("occurred_from", occurredFrom);
  if (occurredTo) params.set("occurred_to", occurredTo);
  return params;
}

async function loadRecordHistory() {
  const params = recordHistoryParams();
  state.historyRecords = await api(`/records?${params}`);
  renderRecordHistory();
}

async function downloadRecordHistoryCsv() {
  if (!state.isSchoolAdmin || !state.historyRecords.length) return;
  const confirmed = await requestConfirmation({
    title: "CSVをダウンロードしますか？",
    message: "現在の検索条件に合う記録をCSVで保存します。園児名と通知内容を含むため、共有端末や第三者へ渡さないでください。LINE ID、音声、文字起こし、内部IDは含まれません。",
    confirmLabel: "CSVをダウンロード",
    confirmIcon: "download",
  });
  if (!confirmed) return;

  elements.recordHistoryExportButton.disabled = true;
  try {
    const params = recordHistoryParams();
    params.delete("limit");
    const response = await fetchWithTimeout(`${apiBase}/records/export.csv?${params}`, {
      headers: {
        Accept: "text/csv",
        ...(state.accessToken ? { Authorization: `Bearer ${state.accessToken}` } : {}),
      },
    });
    if (!response.ok) {
      let message = "CSVをダウンロードできませんでした。";
      try {
        const body = await response.json();
        if (typeof body.detail === "string") message = body.detail;
      } catch {
        // Do not surface an unexpected response body containing private data.
      }
      throw new Error(message);
    }
    const file = await response.blob();
    const downloadUrl = URL.createObjectURL(file);
    const link = document.createElement("a");
    link.href = downloadUrl;
    link.download = `small-step-record-history-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(downloadUrl), 0);
    setNotice("記録履歴のCSVをダウンロードしました。取り扱いに注意してください。");
  } catch (error) {
    setNotice(error.message, true);
  } finally {
    if (elements.recordHistoryExportButton.isConnected) {
      elements.recordHistoryExportButton.disabled = !state.historyRecords.length;
    }
  }
}

async function loadNotifications() {
  state.notifications = await api(`/notifications?school_id=${encodeURIComponent(state.schoolId)}`);
  if (!state.notifications.some((item) => item.id === state.reschedulingNotificationId && ["pending", "waiting_guardian_link"].includes(item.status))) {
    state.reschedulingNotificationId = null;
  }
  renderNotifications();
}

async function syncNotificationToNotion(recordId) {
  const notification = state.notifications.find((item) => item.record_id === recordId);
  if (!state.isSchoolAdmin || !notification || notification.status !== "sent" || notification.notion_synced_at) return;

  const confirmed = await requestConfirmation({
    title: "Notionに記録しますか？",
    message: "LINE送信済みの承認内容をNotionへ記録します。同じ通知をもう一度記録することはありません。",
    confirmLabel: "Notionに記録",
    confirmIcon: "description",
  });
  if (!confirmed) return;

  try {
    await withLoading(async () => {
      await api(`/records/${recordId}/notion-sync`, { method: "POST" });
      await loadNotifications();
    });
    setNotice("Notionに記録しました。");
  } catch (error) {
    setNotice(error.message, true);
  }
}

async function cancelNotification(notificationId) {
  const notification = state.notifications.find((item) => item.id === notificationId);
  if (!state.isSchoolAdmin || !notification || !["pending", "waiting_guardian_link"].includes(notification.status)) return;

  const confirmed = await requestConfirmation({
    title: "配信を取消しますか？",
    message: notification.status === "waiting_guardian_link"
      ? "保護者LINEの連携待ちを取り消します。後で連携しても、この通知は送信されません。"
      : "送信待ちの通知だけを取り消せます。LINE送信が始まった通知は取り消せません。",
    confirmLabel: "配信を取消",
    confirmIcon: "block",
  });
  if (!confirmed) return;

  try {
    await withLoading(async () => {
      await api(`/notifications/${notificationId}/cancel`, { method: "POST" });
      await loadNotifications();
    });
    setNotice(notification.status === "waiting_guardian_link"
      ? "保護者LINEの連携待ち通知を取り消しました。"
      : "送信前の通知を取り消しました。");
  } catch (error) {
    setNotice(error.message, true);
  }
}

async function rescheduleNotification(notificationId, value) {
  const notification = state.notifications.find((item) => item.id === notificationId);
  const scheduledMilliseconds = Date.parse(value);
  if (!state.isSchoolAdmin || !notification || !["pending", "waiting_guardian_link"].includes(notification.status)) return;
  if (!value || !Number.isFinite(scheduledMilliseconds) || scheduledMilliseconds <= Date.now()) {
    setNotice("現在より後の配信日時を入力してください。", true);
    return;
  }

  const scheduledFor = new Date(scheduledMilliseconds).toISOString();
  const confirmed = await requestConfirmation({
    title: "配信日時を変更しますか？",
    message: notification.status === "waiting_guardian_link"
      ? `保護者がLINE連携した後、${formatDate(scheduledFor)}に通知するよう予約します。`
      : `${formatDate(scheduledFor)}に保護者へ通知するよう予約します。送信開始後は変更できません。`,
    confirmLabel: "この日時で予約",
    confirmIcon: "schedule",
  });
  if (!confirmed) return;

  try {
    await withLoading(async () => {
      await api(`/notifications/${notificationId}/schedule`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scheduled_for: scheduledFor }),
      });
      state.reschedulingNotificationId = null;
      await loadNotifications();
    });
    setNotice(`配信予定を${formatDate(scheduledFor)}へ変更しました。`);
  } catch (error) {
    setNotice(error.message, true);
  }
}

async function retryNotification(notificationId) {
  const notification = state.notifications.find((item) => item.id === notificationId);
  if (!state.isSchoolAdmin || !notification || notification.status !== "failed") return;

  const confirmed = await requestConfirmation({
    title: "LINE通知を再送予約しますか？",
    message: "通知を送信待ちへ戻します。LINE送信ワーカーが次の確認時に配信します。",
    confirmLabel: "再送を予約",
    confirmIcon: "refresh",
  });
  if (!confirmed) return;

  try {
    await withLoading(async () => {
      await api(`/notifications/${notificationId}/retry`, { method: "POST" });
      await loadNotifications();
    });
    setNotice("LINE通知を再送予約しました。");
  } catch (error) {
    setNotice(error.message, true);
  }
}

async function loadAudioJobs() {
  state.audioJobs = await api(`/audio-jobs?school_id=${encodeURIComponent(state.schoolId)}`);
  renderAudioJobs();
}

function auditEventParams() {
  const params = new URLSearchParams({ school_id: state.schoolId, limit: "100" });
  const action = elements.auditEventsActionSelect.value;
  const occurredFrom = dateFilterToIso(elements.auditEventsFrom.value);
  const occurredTo = dateFilterToIso(elements.auditEventsTo.value, true);
  if (action) params.set("action", action);
  if (occurredFrom) params.set("occurred_from", occurredFrom);
  if (occurredTo) params.set("occurred_to", occurredTo);
  return params;
}

async function loadAuditEvents() {
  if (!state.isSchoolAdmin) {
    state.auditEvents = [];
    renderAuditEventManagement();
    return;
  }
  state.auditEvents = await api(`/audit-events?${auditEventParams()}`);
  renderAuditEventManagement();
}

async function loadRuntimeReadiness() {
  if (!state.isSchoolAdmin) {
    state.runtimeReadiness = null;
    renderRuntimeReadiness();
    return;
  }
  const response = await fetchWithTimeout(`${apiBase}/readiness`, {
    headers: {
      Accept: "application/json",
      ...(state.accessToken ? { Authorization: `Bearer ${state.accessToken}` } : {}),
    },
  });
  let readiness;
  try {
    readiness = await response.json();
  } catch {
    throw new Error("稼働準備の状態を読み込めませんでした。");
  }
  if (!response.ok && response.status !== 503) {
    throw new Error("稼働準備の状態を読み込めませんでした。");
  }
  state.runtimeReadiness = readiness;
  renderRuntimeReadiness();
}

async function downloadAuditHistoryCsv() {
  if (!state.isSchoolAdmin || !state.auditEvents.length) return;
  const confirmed = await requestConfirmation({
    title: "CSVをダウンロードしますか？",
    message: "現在の絞り込み条件に合う操作履歴をCSVで保存します。園児名、通知文、音声、LINE情報、接続用キーは含まれません。実行者の表示名は含まれるため、園の運用管理以外には共有しないでください。",
    confirmLabel: "CSVをダウンロード",
    confirmIcon: "download",
  });
  if (!confirmed) return;

  elements.auditEventsExportButton.disabled = true;
  try {
    const params = auditEventParams();
    params.delete("limit");
    const response = await fetchWithTimeout(`${apiBase}/audit-events/export.csv?${params}`, {
      headers: {
        Accept: "text/csv",
        ...(state.accessToken ? { Authorization: `Bearer ${state.accessToken}` } : {}),
      },
    });
    if (!response.ok) {
      let message = "操作履歴のCSVをダウンロードできませんでした。";
      try {
        const body = await response.json();
        if (typeof body.detail === "string") message = body.detail;
      } catch {
        // Do not surface an unexpected response body containing private data.
      }
      throw new Error(message);
    }
    const file = await response.blob();
    const downloadUrl = URL.createObjectURL(file);
    const link = document.createElement("a");
    link.href = downloadUrl;
    link.download = `small-step-audit-history-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(downloadUrl), 0);
    await loadAuditEvents();
    setNotice("操作履歴のCSVをダウンロードしました。取り扱いに注意してください。");
  } catch (error) {
    setNotice(error.message, true);
  } finally {
    if (elements.auditEventsExportButton.isConnected) {
      elements.auditEventsExportButton.disabled = !state.auditEvents.length;
    }
  }
}

async function loadTeachers() {
  if (!state.isSchoolAdmin) {
    state.teachers = [];
    renderTeacherManagement();
    return;
  }
  state.teachers = await api(`/teachers?school_id=${encodeURIComponent(state.schoolId)}`);
  renderTeacherManagement();
}

async function loadEdgeDevices() {
  if (!state.isSchoolAdmin) {
    state.edgeDevices = [];
    renderEdgeDeviceManagement();
    return;
  }
  state.edgeDevices = await api(`/edge-devices?school_id=${encodeURIComponent(state.schoolId)}`);
  renderEdgeDeviceManagement();
}

async function loadVoiceConsent() {
  if (state.authConfig?.auth_mode === "development") {
    state.voiceConsent = null;
    renderVoiceConsent();
    return;
  }
  state.voiceConsent = await api("/voice-consent/me");
  renderVoiceConsent();
}

async function loadApp() {
  return withLoading(async () => {
    const schools = await api("/schools");
    if (!schools.length) throw new Error("園がまだ登録されていません。先に園を作成してください。");
    state.schools = schools;
    state.schoolId = state.schoolId && schools.some((school) => school.id === state.schoolId)
      ? state.schoolId
      : schools[0].id;
    renderSchoolOptions(schools);
    renderSchoolSettings();
    await Promise.all([
      loadRecords(),
      loadNotifications(),
      loadAudioJobs(),
      loadTeachers(),
      loadVoiceConsent(),
      loadActiveLineLinkInvitations(),
    ]);
    await loadEdgeDevices();
  });
}

async function changeView(view) {
  if (!state.isSchoolAdmin && isSchoolAdminOnlyView(view)) view = "home";
  state.activeView = view;
  elements.homeView.hidden = view !== "home";
  elements.reviewView.hidden = view !== "review";
  elements.recordHistoryView.hidden = view !== "record-history";
  elements.notificationsView.hidden = view !== "notifications";
  elements.audioJobsView.hidden = view !== "audio-jobs";
  elements.childrenView.hidden = view !== "children";
  elements.schoolSettingsView.hidden = view !== "school-settings";
  elements.teachersView.hidden = view !== "teachers";
  elements.edgeDevicesView.hidden = view !== "edge-devices";
  elements.runtimeView.hidden = view !== "runtime";
  elements.auditEventsView.hidden = view !== "audit-events";
  elements.voiceConsentView.hidden = view !== "voice-consent";
  for (const button of elements.navButtons) {
    const isActive = button.dataset.view === view;
    button.classList.toggle("is-active", isActive);
    if (isActive) {
      button.setAttribute("aria-current", "page");
    } else {
      button.removeAttribute("aria-current");
    }
  }
  if (view === "notifications") {
    try {
      await withLoading(() => loadNotifications());
    } catch (error) {
      setNotice(error.message, true);
    }
  }
  if (view === "record-history") {
    try {
      await withLoading(() => loadRecordHistory());
    } catch (error) {
      setNotice(error.message, true);
    }
  }
  if (view === "audio-jobs") {
    try {
      await withLoading(() => loadAudioJobs());
    } catch (error) {
      setNotice(error.message, true);
    }
  }
  if (view === "voice-consent") {
    try {
      await withLoading(() => loadVoiceConsent());
    } catch (error) {
      setNotice(error.message, true);
    }
  }
  if (view === "edge-devices") {
    try {
      await withLoading(() => loadEdgeDevices());
    } catch (error) {
      setNotice(error.message, true);
    }
  }
  if (view === "school-settings") renderSchoolSettings();
  if (view === "runtime") {
    try {
      await withLoading(() => loadRuntimeReadiness());
    } catch (error) {
      setNotice(error.message, true);
    }
  }
  if (view === "audit-events") {
    try {
      await withLoading(() => loadAuditEvents());
    } catch (error) {
      setNotice(error.message, true);
    }
  }
}

async function saveVoiceConsent() {
  if (!elements.voiceConsentCheckbox.checked) return;
  const retentionDays = Number(elements.voiceConsentRetentionDays.value);
  if (!Number.isInteger(retentionDays) || retentionDays < 1 || retentionDays > 365) {
    setNotice("同意の有効期間は1日から365日の範囲で入力してください。", true);
    return;
  }
  elements.voiceConsentSubmitButton.disabled = true;
  try {
    state.voiceConsent = await api("/voice-consent/me", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ accepts_voiceprint_enrollment: true, retention_days: retentionDays }),
    });
    elements.voiceConsentCheckbox.checked = false;
    renderVoiceConsent();
    setNotice("声紋登録への同意を保存しました。声紋や音声はまだ登録されていません。");
  } catch (error) {
    setNotice(error.message, true);
  } finally {
    elements.voiceConsentSubmitButton.disabled = false;
  }
}

async function revokeVoiceConsent() {
  const confirmed = await requestConfirmation({
    title: "声紋登録への同意を取り消しますか？",
    message: "以後の声紋登録は開始できなくなります。現在は音声や声紋の特徴量を保存していないため、削除対象の声紋はありません。",
    confirmLabel: "同意を取り消す",
    confirmIcon: "close",
  });
  if (!confirmed) return;
  elements.voiceConsentRevokeButton.disabled = true;
  try {
    state.voiceConsent = await api("/voice-consent/me/revoke", { method: "POST" });
    renderVoiceConsent();
    setNotice("声紋登録への同意を取り消しました。声紋や音声はまだ登録されていません。");
  } catch (error) {
    setNotice(error.message, true);
  } finally {
    elements.voiceConsentRevokeButton.disabled = false;
  }
}

async function createTeacher() {
  const name = elements.teacherNameInput.value.trim();
  const email = elements.teacherEmailInput.value.trim();
  if (!name || !email) return;
  elements.teacherCreateButton.disabled = true;
  try {
    await api("/teachers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ school_id: state.schoolId, name, email, role: "teacher" }),
    });
    elements.teacherNameInput.value = "";
    elements.teacherEmailInput.value = "";
    setNotice("先生を登録しました。次にSupabase Dashboardから同じメールアドレスへ招待を送ってください。");
    await loadTeachers();
  } catch (error) {
    setNotice(error.message, true);
  } finally {
    elements.teacherCreateButton.disabled = false;
  }
}

function openManualRecordForm() {
  if (!state.children.length) {
    setNotice("先に園児を登録してください。", true);
    return;
  }
  state.manualRecordMode = true;
  state.selectedRecordId = null;
  elements.manualRecordForm.reset();
  elements.manualRecordOccurredAtInput.value = dateTimeLocalValue(new Date().toISOString());
  render();
  queueMicrotask(() => elements.manualRecordChildSelect.focus());
}

function closeManualRecordForm() {
  state.manualRecordMode = false;
  state.selectedRecordId = state.records[0]?.id ?? null;
  render();
}

async function createManualRecord() {
  const childId = elements.manualRecordChildSelect.value;
  const occurredAt = elements.manualRecordOccurredAtInput.value;
  const summary = elements.manualRecordSummaryInput.value.trim();
  const conversationPrompt = elements.manualRecordPromptInput.value.trim();
  if (!childId || !occurredAt || !summary) return;
  const occurredAtMilliseconds = Date.parse(occurredAt);
  if (!Number.isFinite(occurredAtMilliseconds) || occurredAtMilliseconds > Date.now()) {
    setNotice("発生日時は現在以前の日時を入力してください。", true);
    elements.manualRecordOccurredAtInput.focus();
    return;
  }
  const payload = {
    school_id: state.schoolId,
    child_id: childId,
    category: elements.manualRecordCategorySelect.value,
    occurred_at: new Date(occurredAtMilliseconds).toISOString(),
    summary,
  };
  if (conversationPrompt) payload.conversation_prompt = conversationPrompt;
  if (state.authConfig?.auth_mode === "development") {
    if (!elements.manualRecordTeacherSelect.value) {
      setNotice("担当先生を登録して選択してください。", true);
      return;
    }
    payload.teacher_id = elements.manualRecordTeacherSelect.value;
  }
  elements.manualRecordCreateButton.disabled = true;
  try {
    const record = await withLoading(() => api("/records/manual", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }));
    state.manualRecordMode = false;
    await loadRecords();
    state.selectedRecordId = record.id;
    render();
    setNotice("手入力の記録をレビュー待ちに追加しました。内容を確認してから承認してください。");
  } catch (error) {
    setNotice(error.message, true);
  } finally {
    elements.manualRecordCreateButton.disabled = false;
  }
}

async function saveSchoolDigestTime() {
  if (!state.isSchoolAdmin || !state.schoolId) return;
  const digestTime = elements.schoolDigestTimeInput.value;
  if (!/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(digestTime)) {
    setNotice("配信時刻を時:分の形式で入力してください。", true);
    elements.schoolDigestTimeInput.focus();
    return;
  }
  const confirmed = await requestConfirmation({
    title: "既定の配信時刻を変更しますか？",
    message: `${digestTime}を、今後承認する成長記録の既定配信時刻にします。すでに送信待ちの通知時刻は変更されません。`,
    confirmLabel: "配信時刻を保存",
    confirmIcon: "schedule",
  });
  if (!confirmed) return;
  elements.schoolDigestTimeSaveButton.disabled = true;
  try {
    const school = await withLoading(() => api(`/schools/${state.schoolId}/digest-time`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ digest_time: digestTime }),
    }));
    state.schools = state.schools.map((item) => item.id === school.id ? school : item);
    renderSchoolOptions(state.schools);
    renderSchoolSettings();
    setNotice(`成長記録の既定配信時刻を${digestTime}に変更しました。`);
  } catch (error) {
    setNotice(error.message, true);
  } finally {
    elements.schoolDigestTimeSaveButton.disabled = !state.isSchoolAdmin;
  }
}

async function disableTeacher(teacherId) {
  const teacher = state.teachers.find((item) => item.id === teacherId);
  if (!teacher || !teacher.is_active) return;
  const confirmed = await requestConfirmation({
    title: `${teacher.name}先生を利用停止にしますか？`,
    message: "Small Stepへのログインを止め、担当の録音端末と待機中の音声処理も停止します。既存の記録・通知は園の履歴として残ります。利用を再開しても、以前の端末キーや声紋同意は復活しません。",
    confirmLabel: "利用停止にする",
    confirmIcon: "block",
  });
  if (!confirmed) return;
  try {
    await withLoading(async () => {
      await api(`/teachers/${teacherId}/disable`, { method: "POST" });
      await Promise.all([loadTeachers(), loadEdgeDevices(), loadAudioJobs()]);
    });
    setNotice("先生アカウントを利用停止にしました。記録と通知の履歴は保持されています。");
  } catch (error) {
    setNotice(error.message, true);
  }
}

async function restoreTeacher(teacherId) {
  const teacher = state.teachers.find((item) => item.id === teacherId);
  if (!teacher || teacher.is_active) return;
  const confirmed = await requestConfirmation({
    title: `${teacher.name}先生の利用を再開しますか？`,
    message: "Small Stepへのログインを再開できます。以前の録音端末、待機中の音声、声紋同意は再開されません。必要な端末は新しいキーで登録してください。",
    confirmLabel: "利用を再開する",
    confirmIcon: "refresh",
  });
  if (!confirmed) return;
  try {
    await withLoading(async () => {
      await api(`/teachers/${teacherId}/restore`, { method: "POST" });
      await Promise.all([loadTeachers(), loadEdgeDevices(), loadAudioJobs()]);
    });
    setNotice("先生アカウントの利用を再開しました。必要なら録音端末と声紋設定を改めて登録してください。");
  } catch (error) {
    setNotice(error.message, true);
  }
}

async function changeTeacherRole(teacherId, role) {
  const teacher = state.teachers.find((item) => item.id === teacherId);
  if (!teacher || !teacher.is_active || !["school_admin", "teacher"].includes(role)) return;
  const isPromotion = role === "school_admin";
  const confirmed = await requestConfirmation({
    title: isPromotion ? `${teacher.name}先生を管理者にしますか？` : `${teacher.name}先生を通常の先生に戻しますか？`,
    message: isPromotion
      ? "園児・保護者、先生、録音端末、通知、操作履歴を管理できるようになります。"
      : "管理者向けの操作ができなくなります。園には別の有効な先生管理者が1人以上必要です。",
    confirmLabel: isPromotion ? "管理者にする" : "先生に戻す",
    confirmIcon: isPromotion ? "admin_panel_settings" : "group",
  });
  if (!confirmed) return;
  try {
    await withLoading(async () => {
      await api(`/teachers/${teacherId}/role`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role }),
      });
      await loadTeachers();
    });
    setNotice(isPromotion ? "先生を管理者にしました。" : "先生を通常の先生に戻しました。");
  } catch (error) {
    setNotice(error.message, true);
  }
}

function showEdgeDeviceKey(device) {
  elements.edgeDeviceKeyTitle.textContent = `${device.name}の接続用キー`;
  elements.edgeDeviceApiKey.textContent = device.api_key;
  elements.edgeDeviceKeyResult.hidden = false;
}

function clearEdgeDeviceKey() {
  elements.edgeDeviceKeyTitle.textContent = "新しい端末";
  elements.edgeDeviceApiKey.textContent = "";
  elements.edgeDeviceKeyResult.hidden = true;
}

async function createEdgeDevice() {
  const name = elements.edgeDeviceNameInput.value.trim();
  const teacherId = elements.edgeDeviceTeacherSelect.value;
  if (!name || !teacherId) return;
  elements.edgeDeviceCreateButton.disabled = true;
  try {
    const device = await api("/edge-devices", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ school_id: state.schoolId, teacher_id: teacherId, name }),
    });
    elements.edgeDeviceNameInput.value = "";
    showEdgeDeviceKey(device);
    await loadEdgeDevices();
    setNotice("録音端末を登録しました。接続用キーは今だけ表示されています。");
  } catch (error) {
    setNotice(error.message, true);
  } finally {
    elements.edgeDeviceCreateButton.disabled = false;
  }
}

async function rotateEdgeDeviceKey(deviceId) {
  const device = state.edgeDevices.find((item) => item.id === deviceId);
  if (!device) return;
  const confirmed = await requestConfirmation({
    title: `${device.name}の鍵を再発行しますか？`,
    message: "現在の鍵はすぐ使えなくなります。新しい鍵を端末へ設定してください。",
    confirmLabel: "鍵を再発行",
    confirmIcon: "key",
  });
  if (!confirmed) return;
  try {
    const rotated = await api(`/edge-devices/${deviceId}/rotate-key`, { method: "POST" });
    showEdgeDeviceKey(rotated);
    await loadEdgeDevices();
    setNotice("接続用キーを再発行しました。古い鍵は無効になっています。");
  } catch (error) {
    setNotice(error.message, true);
  }
}

async function disableEdgeDevice(deviceId) {
  const device = state.edgeDevices.find((item) => item.id === deviceId);
  if (!device) return;
  const confirmed = await requestConfirmation({
    title: `${device.name}を無効化しますか？`,
    message: "この端末からの音声送信はすぐに拒否されます。再開するときは鍵を再発行してください。",
    confirmLabel: "端末を無効化",
    confirmIcon: "block",
  });
  if (!confirmed) return;
  try {
    await api(`/edge-devices/${deviceId}/disable`, { method: "POST" });
    await loadEdgeDevices();
    setNotice("録音端末を無効化しました。");
  } catch (error) {
    setNotice(error.message, true);
  }
}

async function copyEdgeDeviceKey() {
  const apiKey = elements.edgeDeviceApiKey.textContent;
  if (!apiKey) return;
  try {
    await navigator.clipboard.writeText(apiKey);
    setNotice("接続用キーをコピーしました。端末の .env に設定してください。");
  } catch {
    setNotice("キーをコピーできませんでした。表示されたキーを手動でコピーしてください。", true);
  }
}

async function createChild() {
  const displayName = elements.childNameInput.value.trim();
  if (!displayName) return;
  elements.childCreateButton.disabled = true;
  try {
    await api("/children", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ school_id: state.schoolId, display_name: displayName }),
    });
    elements.childNameInput.value = "";
    setNotice("園児を追加しました。");
    await loadRecords();
  } catch (error) {
    setNotice(error.message, true);
  } finally {
    elements.childCreateButton.disabled = false;
  }
}

async function updateChild(childId, displayName) {
  if (!displayName) return;
  try {
    await api(`/children/${childId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ display_name: displayName }),
    });
    state.editingChildId = null;
    await loadRecords();
    setNotice("園児の表示名を更新しました。過去の記録はそのまま保持されています。");
  } catch (error) {
    setNotice(error.message, true);
  }
}

async function archiveChild(childId) {
  const child = state.allChildren.find((item) => item.id === childId);
  if (!child || !child.is_active) return;
  const confirmed = await requestConfirmation({
    title: `${child.display_name}さんを退園処理しますか？`,
    message: "LINE連携、未使用の招待コード、保護者用アーカイブURLを無効にします。未確認の記録、未送信通知、未処理の音声も停止します。送信済みの通知と過去の記録は履歴として残ります。",
    confirmLabel: "退園処理する",
    confirmIcon: "person_remove",
  });
  if (!confirmed) return;

  try {
    await withLoading(async () => {
      await api(`/children/${childId}/archive`, { method: "POST" });
      state.editingChildId = null;
      clearInvitationCode();
      clearGuardianArchiveUrl();
      await Promise.all([loadRecords(), loadNotifications(), loadAudioJobs(), loadActiveLineLinkInvitations()]);
      if (state.activeView === "record-history") await loadRecordHistory();
    });
    setNotice("退園処理を完了しました。新しい通知と音声処理は停止し、履歴は保持されています。");
  } catch (error) {
    setNotice(error.message, true);
  }
}

async function restoreChild(childId) {
  const child = state.allChildren.find((item) => item.id === childId);
  if (!child || child.is_active) return;
  const confirmed = await requestConfirmation({
    title: `${child.display_name}さんを復園に戻しますか？`,
    message: "園児を在籍中の一覧へ戻します。以前の保護者LINE連携、招待コード、配信アーカイブURL、未送信通知、未処理音声は復活しません。必要なら新しい招待コードを発行してください。",
    confirmLabel: "復園に戻す",
    confirmIcon: "refresh",
  });
  if (!confirmed) return;

  try {
    await withLoading(async () => {
      await api(`/children/${childId}/restore`, { method: "POST" });
      clearInvitationCode();
      clearGuardianArchiveUrl();
      await Promise.all([loadRecords(), loadNotifications(), loadAudioJobs(), loadActiveLineLinkInvitations()]);
      if (state.activeView === "record-history") await loadRecordHistory();
    });
    setNotice("復園として在籍中の一覧へ戻しました。保護者LINEは新しい招待コードで連携してください。");
  } catch (error) {
    setNotice(error.message, true);
  }
}

async function createLinkInvitation(childId) {
  const child = state.children.find((item) => item.id === childId);
  if (!child) return;
  const currentInvitation = state.lineLinkInvitations.find((item) => item.child_id === childId);
  if (currentInvitation) {
    const confirmed = await requestConfirmation({
      title: "新しい招待コードを発行しますか？",
      message: `現在のコードは${formatDate(currentInvitation.expires_at)}まで有効ですが、新しいコードを発行するとすぐ使えなくなります。`,
      confirmLabel: "新しいコードを発行",
      confirmIcon: "person_add",
    });
    if (!confirmed) return;
  }
  try {
    setNotice("LINE招待コードを発行しています...");
    const invitation = await api("/line/link-invitations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ child_id: childId, expires_in_minutes: 60 }),
    });
    elements.inviteChildName.textContent = `${child.display_name}さんの保護者用コード`;
    elements.inviteExpiration.textContent = formatDate(invitation.expires_at);
    elements.inviteCode.textContent = invitation.invite_code;
    elements.inviteResult.hidden = false;
    await loadActiveLineLinkInvitations();
    setNotice(currentInvitation
      ? "新しい招待コードを発行しました。以前のコードは使えません。"
      : "招待コードを発行しました。保護者へコードだけを送ってください。");
  } catch (error) {
    setNotice(error.message, true);
  }
}

async function copyInvitationCode() {
  const code = elements.inviteCode.textContent;
  if (!code) return;
  try {
    await navigator.clipboard.writeText(code);
    setNotice("招待コードをコピーしました。");
  } catch {
    setNotice("コードをコピーできませんでした。表示されたコードを手動でコピーしてください。", true);
  }
}

function showGuardianArchiveUrl(child, archiveLink) {
  elements.guardianArchiveChildName.textContent = `${child.display_name}さんの保護者用URL`;
  elements.guardianArchiveExpiration.textContent = formatDate(archiveLink.expires_at);
  elements.guardianArchiveUrl.textContent = archiveLink.archive_url;
  elements.guardianArchiveResult.hidden = false;
}

function clearGuardianArchiveUrl() {
  elements.guardianArchiveChildName.textContent = "";
  elements.guardianArchiveExpiration.textContent = "";
  elements.guardianArchiveUrl.textContent = "";
  elements.guardianArchiveResult.hidden = true;
}

function clearInvitationCode() {
  elements.inviteChildName.textContent = "";
  elements.inviteExpiration.textContent = "";
  elements.inviteCode.textContent = "";
  elements.inviteResult.hidden = true;
}

async function createGuardianArchiveLink(childId) {
  const child = state.children.find((item) => item.id === childId);
  if (!child) return;
  const confirmed = await requestConfirmation({
    title: `${child.display_name}さんのアーカイブURLを発行しますか？`,
    message: "以前に発行したURLはすぐ使えなくなります。URLは保護者本人とのLINEトークにだけ送ってください。",
    confirmLabel: "URLを発行",
    confirmIcon: "link",
  });
  if (!confirmed) return;
  try {
    const archiveLink = await api("/guardian-archive-links", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ child_id: childId }),
    });
    showGuardianArchiveUrl(child, archiveLink);
    setNotice("保護者用の配信アーカイブURLを発行しました。URLは今だけ表示されています。");
  } catch (error) {
    setNotice(error.message, true);
  }
}

async function copyGuardianArchiveUrl() {
  const archiveUrl = elements.guardianArchiveUrl.textContent;
  if (!archiveUrl) return;
  try {
    await navigator.clipboard.writeText(archiveUrl);
    setNotice("保護者用URLをコピーしました。保護者本人とのLINEトークへ個別に送ってください。");
  } catch {
    setNotice("URLをコピーできませんでした。表示されたURLを手動でコピーしてください。", true);
  }
}

async function unlinkGuardianLineAccount(childId) {
  const child = state.children.find((item) => item.id === childId);
  if (!child || !child.guardian_line_user_id) return;

  const confirmed = await requestConfirmation({
    title: `${child.display_name}さんのLINE連携を解除しますか？`,
    message: "未送信の通知、未使用の招待コード、保護者用アーカイブURLはすぐ無効になります。すでにLINEへ送信を開始した通知は取り消せません。",
    confirmLabel: "LINE連携を解除",
    confirmIcon: "link_off",
  });
  if (!confirmed) return;

  try {
    await api(`/children/${childId}/guardian-line-link`, { method: "DELETE" });
    clearInvitationCode();
    clearGuardianArchiveUrl();
    await Promise.all([loadRecords(), loadNotifications(), loadActiveLineLinkInvitations()]);
    setNotice("保護者LINEの連携を解除しました。新しい保護者へ連携し直す場合は、招待コードを発行してください。");
  } catch (error) {
    setNotice(error.message, true);
  }
}

async function submitReview(action) {
  const record = selectedRecord();
  if (!record) return;
  const actionLabel = action === "approve" ? "承認" : "却下";
  const childId = action === "approve" ? elements.childSelect.value : "";
  if (action === "approve" && !childId) {
    setNotice("園児を選択してから承認してください。", true);
    elements.childSelect.focus();
    return;
  }
  let scheduledFor = null;
  if (action === "approve" && elements.scheduledForEnabled.checked) {
    const value = elements.scheduledForInput.value;
    const scheduledMilliseconds = Date.parse(value);
    if (!value || !Number.isFinite(scheduledMilliseconds)) {
      setNotice("指定する配信日時を入力してください。", true);
      elements.scheduledForInput.focus();
      return;
    }
    scheduledFor = new Date(scheduledMilliseconds).toISOString();
  }
  const confirmed = await requestConfirmation({
    title: `記録を${actionLabel}しますか？`,
    message: action === "approve"
      ? scheduledFor
        ? `${record.confidence < lowConfidenceThreshold ? "AIの信頼度が低い候補です。内容を再確認してください。 " : ""}編集内容を保存し、${formatDate(scheduledFor)}に保護者へ通知するよう予約します。`
        : `${record.confidence < lowConfidenceThreshold ? "AIの信頼度が低い候補です。内容を再確認してください。 " : ""}編集内容を保存し、既定の配信ルールで保護者への通知を準備します。`
      : "この記録はレビュー待ちの一覧から削除されます。",
    confirmLabel: actionLabel,
    confirmIcon: action === "approve" ? "check" : "close",
  });
  if (!confirmed) return;

  elements.approveButton.disabled = true;
  elements.rejectButton.disabled = true;
  try {
    if (action === "approve") {
      const payload = {
        child_id: childId,
        summary: elements.summaryInput.value.trim(),
      };
      const prompt = elements.promptInput.value.trim();
      if (prompt) payload.conversation_prompt = prompt;
      if (scheduledFor) payload.scheduled_for = scheduledFor;
      await api(`/records/${record.id}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    } else {
      await api(`/records/${record.id}/reject`, { method: "POST" });
    }
    await Promise.all([loadRecords(), loadNotifications()]);
    if (action === "approve") {
      const notification = state.notifications.find((item) => item.record_id === record.id);
      const deliveryTime = notification ? `配信予定: ${formatDate(notification.scheduled_for)}` : "通知状況を確認してください。";
      setNotice(`記録を承認しました。${deliveryTime}`);
    } else {
      setNotice("記録を却下しました。");
    }
  } catch (error) {
    setNotice(error.message, true);
  } finally {
    elements.approveButton.disabled = false;
    elements.rejectButton.disabled = false;
  }
}

async function linkOrBootstrapTeacher() {
  try {
    const teacher = await api("/auth/link-teacher", { method: "POST" });
    await openAppForTeacher(teacher);
  } catch (error) {
    if (error.status !== 404) throw error;
    const schools = await api("/auth/bootstrap/schools");
    if (!schools.length) throw new Error("紐付ける園がありません。先に園を登録してください。");
    elements.bootstrapSchoolSelect.replaceChildren();
    for (const school of schools) {
      const option = document.createElement("option");
      option.value = school.id;
      option.textContent = school.name;
      elements.bootstrapSchoolSelect.append(option);
    }
    elements.loginForm.hidden = true;
    elements.bootstrapPanel.hidden = false;
    setLoginNotice("初回設定として、管理する園と表示名を登録してください。");
  }
}

async function establishTeacherSession() {
  try {
    const teacher = await api("/auth/me");
    await openAppForTeacher(teacher);
  } catch (error) {
    if (error.status !== 403) throw error;
    await linkOrBootstrapTeacher();
  }
}

async function openAppForTeacher(teacher) {
  state.isSchoolAdmin = teacher.role === "school_admin";
  state.currentTeacherId = teacher.id;
  applySchoolAdminVisibility();
  showApp();
  await changeView("home");
  await loadApp();
}

async function signInWithPassword() {
  const email = elements.loginEmail.value.trim();
  const password = elements.loginPassword.value;
  const { supabase_url: supabaseUrl, supabase_publishable_key: publishableKey } = state.authConfig;
  if (!supabaseUrl || !publishableKey) throw new Error("Supabaseの公開設定が不足しています。");

  const response = await fetchWithTimeout(`${supabaseUrl.replace(/\/$/, "")}/auth/v1/token?grant_type=password`, {
    method: "POST",
    headers: { apikey: publishableKey, "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const body = await response.json();
  if (!response.ok || typeof body.access_token !== "string") {
    throw new Error(body.error_description || body.message || "メールアドレスまたはパスワードを確認してください。");
  }
  state.accessToken = body.access_token;
  sessionStorage.setItem(accessTokenStorageKey, body.access_token);
  elements.loginPassword.value = "";
  await establishTeacherSession();
}

async function start() {
  state.authConfig = await api("/auth/config");
  if (state.authConfig.auth_mode === "development") {
    state.isSchoolAdmin = true;
    applySchoolAdminVisibility();
    showApp();
    await loadApp();
    return;
  }
  showLogin();
  if (state.accessToken) {
    try {
      await establishTeacherSession();
    } catch {
      state.accessToken = null;
      sessionStorage.removeItem(accessTokenStorageKey);
      setLoginNotice("ログインし直してください。", true);
    }
  }
}

elements.loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  elements.loginButton.disabled = true;
  try {
    setLoginNotice("ログインしています...");
    await signInWithPassword();
    setLoginNotice("");
  } catch (error) {
    setLoginNotice(error.message, true);
  } finally {
    elements.loginButton.disabled = false;
  }
});

elements.bootstrapForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  elements.bootstrapButton.disabled = true;
  try {
    setLoginNotice("管理者を登録しています...");
    const teacher = await api("/auth/bootstrap/teacher", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        school_id: elements.bootstrapSchoolSelect.value,
        name: elements.bootstrapName.value.trim(),
      }),
    });
    setLoginNotice("");
    await openAppForTeacher(teacher);
  } catch (error) {
    setLoginNotice(error.message, true);
  } finally {
    elements.bootstrapButton.disabled = false;
  }
});

elements.logoutButton.addEventListener("click", async () => {
  state.accessToken = null;
  state.isSchoolAdmin = false;
  state.currentTeacherId = null;
  state.manualRecordMode = false;
  state.reschedulingNotificationId = null;
  state.edgeDevices = [];
  state.audioJobs = [];
  state.auditEvents = [];
  state.teachers = [];
  state.runtimeReadiness = null;
  state.voiceConsent = null;
  state.children = [];
  state.allChildren = [];
  state.lineLinkInvitations = [];
  state.records = [];
  state.historyRecords = [];
  state.editingChildId = null;
  clearEdgeDeviceKey();
  clearInvitationCode();
  clearGuardianArchiveUrl();
  sessionStorage.removeItem(accessTokenStorageKey);
  applySchoolAdminVisibility();
  await changeView("home");
  showLogin();
  setLoginNotice("ログアウトしました。");
});

elements.schoolSelect.addEventListener("change", async (event) => {
  state.schoolId = event.target.value;
  state.selectedRecordId = null;
  state.manualRecordMode = false;
  state.reschedulingNotificationId = null;
  state.editingChildId = null;
  state.historyRecords = [];
  state.auditEvents = [];
  clearEdgeDeviceKey();
  clearInvitationCode();
  clearGuardianArchiveUrl();
  renderSchoolSettings();
  try {
    await withLoading(async () => {
      await Promise.all([loadRecords(), loadNotifications(), loadAudioJobs(), loadTeachers(), loadActiveLineLinkInvitations()]);
      await loadEdgeDevices();
    });
  } catch (error) {
    setNotice(error.message, true);
  }
});

elements.reloadButton.addEventListener("click", async () => {
  try {
    await loadApp();
  } catch (error) {
    setNotice(error.message, true);
  }
});

elements.schoolSettingsForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await saveSchoolDigestTime();
});

elements.notificationFilterForm.addEventListener("submit", (event) => {
  event.preventDefault();
  renderNotifications();
});

elements.notificationFilterResetButton.addEventListener("click", () => {
  elements.notificationStatusSelect.value = "";
  elements.notificationSearch.value = "";
  renderNotifications();
});

elements.recordList.addEventListener("click", (event) => {
  const item = event.target.closest("[data-record-id]");
  if (!item) return;
  state.selectedRecordId = item.dataset.recordId;
  state.manualRecordMode = false;
  render();
});

elements.manualRecordOpenButton.addEventListener("click", () => openManualRecordForm());
elements.manualRecordCancelButton.addEventListener("click", () => closeManualRecordForm());
elements.manualRecordForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await createManualRecord();
});

elements.notificationList.addEventListener("click", async (event) => {
  const guardianLinkButton = event.target.closest("[data-notification-guardian-link-child-id]");
  if (guardianLinkButton) {
    await changeView("children");
    return;
  }
  const closeRescheduleButton = event.target.closest("[data-notification-reschedule-close-id]");
  if (closeRescheduleButton) {
    state.reschedulingNotificationId = null;
    renderNotifications();
    return;
  }

  const rescheduleButton = event.target.closest("[data-notification-reschedule-id]");
  if (rescheduleButton) {
    const notificationId = rescheduleButton.dataset.notificationRescheduleId;
    state.reschedulingNotificationId = state.reschedulingNotificationId === notificationId ? null : notificationId;
    renderNotifications();
    if (state.reschedulingNotificationId) {
      queueMicrotask(() => {
        elements.notificationList.querySelector("[data-notification-reschedule-form] input")?.focus();
      });
    }
    return;
  }

  const cancelButton = event.target.closest("[data-notification-cancel-id]");
  if (cancelButton) {
    cancelButton.disabled = true;
    try {
      await cancelNotification(cancelButton.dataset.notificationCancelId);
    } finally {
      cancelButton.disabled = false;
    }
    return;
  }

  const retryButton = event.target.closest("[data-notification-retry-id]");
  if (retryButton) {
    retryButton.disabled = true;
    try {
      await retryNotification(retryButton.dataset.notificationRetryId);
    } finally {
      retryButton.disabled = false;
    }
    return;
  }

  const notionButton = event.target.closest("[data-notion-sync-record-id]");
  if (!notionButton) return;
  notionButton.disabled = true;
  try {
    await syncNotificationToNotion(notionButton.dataset.notionSyncRecordId);
  } finally {
    notionButton.disabled = false;
  }
});

elements.notificationList.addEventListener("submit", async (event) => {
  const form = event.target.closest("[data-notification-reschedule-form]");
  if (!form) return;
  event.preventDefault();
  const saveButton = form.querySelector('button[type="submit"]');
  saveButton.disabled = true;
  try {
    await rescheduleNotification(form.dataset.notificationRescheduleForm, form.elements.scheduled_for.value);
  } finally {
    if (saveButton.isConnected) saveButton.disabled = false;
  }
});

for (const button of elements.navButtons) {
  button.addEventListener("click", async () => changeView(button.dataset.view));
}

for (const button of elements.homeActions) {
  button.addEventListener("click", async () => changeView(button.dataset.viewTarget));
}

elements.reviewForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await submitReview("approve");
});

elements.rejectButton.addEventListener("click", async () => submitReview("reject"));

elements.summaryInput.addEventListener("input", () => {
  updateCharacterCount(elements.summaryInput, elements.summaryCount);
});

elements.promptInput.addEventListener("input", () => {
  updateCharacterCount(elements.promptInput, elements.promptCount);
});

elements.scheduledForEnabled.addEventListener("change", () => {
  elements.scheduledForInput.disabled = !elements.scheduledForEnabled.checked;
  if (!elements.scheduledForEnabled.checked) elements.scheduledForInput.value = "";
  if (elements.scheduledForEnabled.checked) elements.scheduledForInput.focus();
});

elements.confirmationCancel.addEventListener("click", () => closeConfirmation("cancel"));
elements.confirmationConfirm.addEventListener("click", () => closeConfirmation("confirm"));
elements.confirmationDialog.addEventListener("cancel", (event) => {
  event.preventDefault();
  closeConfirmation("cancel");
});
elements.confirmationDialog.addEventListener("close", finishConfirmation);

elements.childForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await createChild();
});

elements.childList.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-child-action]");
  if (!button) return;
  if (button.dataset.childAction === "edit") {
    state.editingChildId = button.dataset.childId;
    renderChildManagement();
    queueMicrotask(() => {
      elements.childList.querySelector("[data-child-edit-form] input")?.focus();
    });
    return;
  }
  if (button.dataset.childAction === "edit-close") {
    state.editingChildId = null;
    renderChildManagement();
    return;
  }
  if (button.dataset.childAction === "archive") {
    await archiveChild(button.dataset.childId);
    return;
  }
  if (button.dataset.childAction === "restore") {
    await restoreChild(button.dataset.childId);
    return;
  }
  if (button.dataset.childAction === "line-invite") {
    await createLinkInvitation(button.dataset.childId);
    return;
  }
  if (button.dataset.childAction === "guardian-archive") {
    await createGuardianArchiveLink(button.dataset.childId);
    return;
  }
  if (button.dataset.childAction === "guardian-unlink") {
    await unlinkGuardianLineAccount(button.dataset.childId);
  }
});

elements.childList.addEventListener("submit", async (event) => {
  const form = event.target.closest("[data-child-edit-form]");
  if (!form) return;
  event.preventDefault();
  const saveButton = form.querySelector('button[type="submit"]');
  saveButton.disabled = true;
  try {
    await updateChild(form.dataset.childEditForm, form.elements.display_name.value.trim());
  } finally {
    if (saveButton.isConnected) saveButton.disabled = false;
  }
});

elements.recordHistoryFilterForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await withLoading(() => loadRecordHistory());
  } catch (error) {
    setNotice(error.message, true);
  }
});

elements.recordHistoryExportButton.addEventListener("click", async () => {
  await downloadRecordHistoryCsv();
});

elements.recordHistoryResetButton.addEventListener("click", async () => {
  elements.recordHistorySearch.value = "";
  elements.recordHistoryChildSelect.value = "";
  elements.recordHistoryStatusSelect.value = "";
  elements.recordHistoryCategorySelect.value = "";
  elements.recordHistoryFrom.value = "";
  elements.recordHistoryTo.value = "";
  try {
    await withLoading(() => loadRecordHistory());
  } catch (error) {
    setNotice(error.message, true);
  }
});

elements.auditEventsFilterForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await withLoading(() => loadAuditEvents());
  } catch (error) {
    setNotice(error.message, true);
  }
});

elements.auditEventsExportButton.addEventListener("click", async () => {
  await downloadAuditHistoryCsv();
});

elements.auditEventsFilterResetButton.addEventListener("click", async () => {
  elements.auditEventsActionSelect.value = "";
  elements.auditEventsFrom.value = "";
  elements.auditEventsTo.value = "";
  try {
    await withLoading(() => loadAuditEvents());
  } catch (error) {
    setNotice(error.message, true);
  }
});

elements.runtimeRefreshButton.addEventListener("click", async () => {
  try {
    await withLoading(() => loadRuntimeReadiness());
  } catch (error) {
    setNotice(error.message, true);
  }
});

elements.copyInviteCodeButton.addEventListener("click", async () => copyInvitationCode());
elements.copyGuardianArchiveUrlButton.addEventListener("click", async () => copyGuardianArchiveUrl());

elements.teacherForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await createTeacher();
});

elements.teacherList.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-teacher-action]");
  if (!button) return;
  if (button.dataset.teacherAction === "promote") {
    await changeTeacherRole(button.dataset.teacherId, "school_admin");
    return;
  }
  if (button.dataset.teacherAction === "demote") {
    await changeTeacherRole(button.dataset.teacherId, "teacher");
    return;
  }
  if (button.dataset.teacherAction === "disable") {
    await disableTeacher(button.dataset.teacherId);
    return;
  }
  if (button.dataset.teacherAction === "restore") {
    await restoreTeacher(button.dataset.teacherId);
  }
});

elements.edgeDeviceForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await createEdgeDevice();
});

elements.edgeDeviceList.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-edge-device-action]");
  if (!button) return;
  if (button.dataset.edgeDeviceAction === "rotate") {
    await rotateEdgeDeviceKey(button.dataset.edgeDeviceId);
  }
  if (button.dataset.edgeDeviceAction === "disable") {
    await disableEdgeDevice(button.dataset.edgeDeviceId);
  }
});

elements.copyEdgeDeviceKeyButton.addEventListener("click", async () => copyEdgeDeviceKey());

elements.voiceConsentForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await saveVoiceConsent();
});

elements.voiceConsentRevokeButton.addEventListener("click", async () => {
  await revokeVoiceConsent();
});

replaceIconPlaceholders();
updateReviewCharacterCounts();
applySchoolAdminVisibility();
changeView(state.activeView);

start().catch((error) => {
  showLogin();
  setLoginNotice(error.message, true);
});
