const apiBase = "/api/v1";
const accessTokenStorageKey = "small-step.access-token";

const state = {
  schoolId: null,
  children: [],
  teachers: [],
  records: [],
  notifications: [],
  selectedRecordId: null,
  activeView: "home",
  authConfig: null,
  accessToken: sessionStorage.getItem(accessTokenStorageKey),
  isSchoolAdmin: false,
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
  reloadButton: document.querySelector("#reload-button"),
  notice: document.querySelector("#notice"),
  loadingIndicator: document.querySelector("#loading-indicator"),
  recordCount: document.querySelector("#record-count"),
  recordList: document.querySelector("#record-list"),
  emptyState: document.querySelector("#empty-state"),
  reviewForm: document.querySelector("#review-form"),
  recordMeta: document.querySelector("#record-meta"),
  recordCategory: document.querySelector("#record-category"),
  childSelect: document.querySelector("#child-select"),
  summaryInput: document.querySelector("#summary-input"),
  summaryCount: document.querySelector("#summary-count"),
  promptInput: document.querySelector("#prompt-input"),
  promptCount: document.querySelector("#prompt-count"),
  rejectButton: document.querySelector("#reject-button"),
  approveButton: document.querySelector("#approve-button"),
  navButtons: document.querySelectorAll(".nav-button"),
  homeView: document.querySelector("#home-view"),
  reviewView: document.querySelector("#review-view"),
  notificationsView: document.querySelector("#notifications-view"),
  childrenView: document.querySelector("#children-view"),
  teachersView: document.querySelector("#teachers-view"),
  homeReviewCount: document.querySelector("#home-review-count"),
  homePendingCount: document.querySelector("#home-pending-count"),
  homeSentCount: document.querySelector("#home-sent-count"),
  homeActions: document.querySelectorAll("[data-view-target]"),
  notificationCount: document.querySelector("#notification-count"),
  notificationList: document.querySelector("#notification-list"),
  childCount: document.querySelector("#child-count"),
  childForm: document.querySelector("#child-form"),
  childNameInput: document.querySelector("#child-name-input"),
  childCreateButton: document.querySelector("#child-create-button"),
  childRoleNote: document.querySelector("#child-role-note"),
  childList: document.querySelector("#child-list"),
  inviteResult: document.querySelector("#invite-result"),
  inviteChildName: document.querySelector("#invite-child-name"),
  inviteExpiration: document.querySelector("#invite-expiration"),
  inviteCode: document.querySelector("#invite-code"),
  copyInviteCodeButton: document.querySelector("#copy-invite-code-button"),
  teachersNavButton: document.querySelector("#teachers-nav-button"),
  teacherCount: document.querySelector("#teacher-count"),
  teacherForm: document.querySelector("#teacher-form"),
  teacherNameInput: document.querySelector("#teacher-name-input"),
  teacherEmailInput: document.querySelector("#teacher-email-input"),
  teacherCreateButton: document.querySelector("#teacher-create-button"),
  teacherList: document.querySelector("#teacher-list"),
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

function createButtonIcon(iconName) {
  const icon = document.createElement("span");
  icon.className = "material-symbols-outlined button-icon";
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = iconName;
  return icon;
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

function categoryLabel(category) {
  return category === "injury" ? "怪我" : "成長記録";
}

function notificationStatusLabel(status) {
  if (status === "sent") return "送信済み";
  if (status === "failed") return "送信失敗";
  return "送信待ち";
}

function childName(childId) {
  return state.children.find((child) => child.id === childId)?.display_name ?? "園児未選択";
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

function renderRecordList() {
  elements.recordCount.textContent = String(state.records.length);
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
    detail.textContent = `${formatDate(record.occurred_at)} - 信頼度 ${Math.round(record.confidence * 100)}%`;
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

function renderDetail() {
  const record = selectedRecord();
  elements.emptyState.hidden = Boolean(record);
  elements.reviewForm.hidden = !record;
  if (!record) {
    elements.summaryInput.value = "";
    elements.promptInput.value = "";
    updateReviewCharacterCounts();
    return;
  }
  elements.recordMeta.textContent = `${formatDate(record.occurred_at)} / 信頼度 ${Math.round(record.confidence * 100)}%`;
  elements.recordCategory.textContent = categoryLabel(record.category);
  elements.summaryInput.value = record.summary;
  elements.promptInput.value = record.conversation_prompt ?? "";
  updateReviewCharacterCounts();
  renderChildOptions(record);
}

function renderHome() {
  elements.homeReviewCount.textContent = String(state.records.length);
  elements.homePendingCount.textContent = String(state.notifications.filter((item) => item.status === "pending").length);
  elements.homeSentCount.textContent = String(state.notifications.filter((item) => item.status === "sent").length);
}

function renderChildManagement() {
  elements.childCount.textContent = String(state.children.length);
  elements.childForm.hidden = !state.isSchoolAdmin;
  elements.childRoleNote.hidden = state.isSchoolAdmin;
  elements.childList.replaceChildren();

  if (!state.children.length) {
    const text = document.createElement("p");
    text.className = "empty-list";
    text.textContent = "園児はまだ登録されていません。";
    elements.childList.append(text);
    return;
  }

  for (const child of state.children) {
    const item = document.createElement("article");
    item.className = "child-item";

    const content = document.createElement("div");
    const name = document.createElement("h3");
    name.textContent = child.display_name;
    const status = document.createElement("span");
    status.className = "guardian-status";
    status.classList.toggle("is-linked", Boolean(child.guardian_line_user_id));
    status.textContent = child.guardian_line_user_id ? "LINE連携済み" : "LINE未連携";
    content.append(name, status);

    item.append(content);
    if (state.isSchoolAdmin && !child.guardian_line_user_id) {
      const inviteButton = document.createElement("button");
      inviteButton.type = "button";
      inviteButton.className = "child-invite-button";
      inviteButton.dataset.childId = child.id;
      setButtonLabel(inviteButton, "person_add", "招待コードを発行");
      item.append(inviteButton);
    }
    elements.childList.append(item);
  }
}

function teacherRoleLabel(role) {
  return role === "school_admin" ? "先生管理者" : "先生";
}

function renderTeacherManagement() {
  elements.teachersNavButton.hidden = !state.isSchoolAdmin;
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
    const role = document.createElement("span");
    role.className = "teacher-role";
    role.textContent = teacherRoleLabel(teacher.role);
    const auth = document.createElement("span");
    auth.className = "teacher-auth-status";
    auth.classList.toggle("is-linked", teacher.is_auth_linked);
    auth.textContent = teacher.is_auth_linked ? "ログイン済み" : "招待待ち";
    status.append(role, auth);

    item.append(identity, status);
    elements.teacherList.append(item);
  }
}

function render() {
  renderRecordList();
  renderDetail();
  renderHome();
  renderChildManagement();
  renderTeacherManagement();
}

function renderNotifications() {
  elements.notificationCount.textContent = String(state.notifications.length);
  elements.notificationList.replaceChildren();
  renderHome();
  if (!state.notifications.length) {
    const text = document.createElement("p");
    text.className = "empty-list";
    text.textContent = "通知はまだありません。";
    elements.notificationList.append(text);
    return;
  }

  for (const notification of state.notifications) {
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
    status.textContent = notificationStatusLabel(notification.status);
    const meta = document.createElement("p");
    meta.className = "notification-meta";
    meta.textContent = notification.sent_at
      ? `送信: ${formatDate(notification.sent_at)}`
      : `配信予定: ${formatDate(notification.scheduled_for)}`;
    item.append(content, status, meta);
    elements.notificationList.append(item);
  }
}

async function loadRecords() {
  const params = new URLSearchParams({ school_id: state.schoolId, record_status: "pending_review" });
  const [children, records] = await Promise.all([
    api(`/children?school_id=${encodeURIComponent(state.schoolId)}`),
    api(`/records?${params}`),
  ]);
  state.children = children;
  state.records = records;
  if (!state.records.some((record) => record.id === state.selectedRecordId)) {
    state.selectedRecordId = state.records[0]?.id ?? null;
  }
  render();
}

async function loadNotifications() {
  state.notifications = await api(`/notifications?school_id=${encodeURIComponent(state.schoolId)}`);
  renderNotifications();
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

async function loadApp() {
  return withLoading(async () => {
    const schools = await api("/schools");
    if (!schools.length) throw new Error("園がまだ登録されていません。先に園を作成してください。");
    state.schoolId = state.schoolId && schools.some((school) => school.id === state.schoolId)
      ? state.schoolId
      : schools[0].id;
    renderSchoolOptions(schools);
    await Promise.all([loadRecords(), loadNotifications(), loadTeachers()]);
  });
}

async function changeView(view) {
  state.activeView = view;
  elements.homeView.hidden = view !== "home";
  elements.reviewView.hidden = view !== "review";
  elements.notificationsView.hidden = view !== "notifications";
  elements.childrenView.hidden = view !== "children";
  elements.teachersView.hidden = view !== "teachers";
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

async function createLinkInvitation(childId) {
  const child = state.children.find((item) => item.id === childId);
  if (!child) return;
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
    setNotice("招待コードを発行しました。保護者へコードだけを送ってください。");
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

async function submitReview(action) {
  const record = selectedRecord();
  if (!record) return;
  const actionLabel = action === "approve" ? "承認" : "却下";
  const confirmed = await requestConfirmation({
    title: `記録を${actionLabel}しますか？`,
    message: action === "approve"
      ? "編集内容を保存し、保護者への通知を準備します。"
      : "この記録はレビュー待ちの一覧から削除されます。",
    confirmLabel: actionLabel,
    confirmIcon: action === "approve" ? "check" : "close",
  });
  if (!confirmed) return;

  elements.approveButton.disabled = true;
  elements.rejectButton.disabled = true;
  try {
    if (action === "approve") {
      const payload = { summary: elements.summaryInput.value.trim() };
      const childId = elements.childSelect.value;
      const prompt = elements.promptInput.value.trim();
      if (childId) payload.child_id = childId;
      if (prompt) payload.conversation_prompt = prompt;
      await api(`/records/${record.id}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    } else {
      await api(`/records/${record.id}/reject`, { method: "POST" });
    }
    setNotice(`記録を${actionLabel}しました。`);
    await Promise.all([loadRecords(), loadNotifications()]);
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
  showApp();
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

elements.logoutButton.addEventListener("click", () => {
  state.accessToken = null;
  state.isSchoolAdmin = false;
  sessionStorage.removeItem(accessTokenStorageKey);
  showLogin();
  setLoginNotice("ログアウトしました。");
});

elements.schoolSelect.addEventListener("change", async (event) => {
  state.schoolId = event.target.value;
  state.selectedRecordId = null;
  try {
    await withLoading(() => Promise.all([loadRecords(), loadNotifications(), loadTeachers()]));
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

elements.recordList.addEventListener("click", (event) => {
  const item = event.target.closest("[data-record-id]");
  if (!item) return;
  state.selectedRecordId = item.dataset.recordId;
  render();
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
  const button = event.target.closest("[data-child-id]");
  if (!button) return;
  await createLinkInvitation(button.dataset.childId);
});

elements.copyInviteCodeButton.addEventListener("click", async () => copyInvitationCode());

elements.teacherForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await createTeacher();
});

updateReviewCharacterCounts();
changeView(state.activeView);

start().catch((error) => {
  showLogin();
  setLoginNotice(error.message, true);
});
