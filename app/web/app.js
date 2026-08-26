const apiBase = "/api/v1";

const state = {
  schoolId: null,
  children: [],
  records: [],
  notifications: [],
  selectedRecordId: null,
  activeView: "home",
};

const elements = {
  schoolSelect: document.querySelector("#school-select"),
  reloadButton: document.querySelector("#reload-button"),
  notice: document.querySelector("#notice"),
  recordCount: document.querySelector("#record-count"),
  recordList: document.querySelector("#record-list"),
  emptyState: document.querySelector("#empty-state"),
  reviewForm: document.querySelector("#review-form"),
  recordMeta: document.querySelector("#record-meta"),
  recordCategory: document.querySelector("#record-category"),
  childSelect: document.querySelector("#child-select"),
  summaryInput: document.querySelector("#summary-input"),
  promptInput: document.querySelector("#prompt-input"),
  rejectButton: document.querySelector("#reject-button"),
  approveButton: document.querySelector("#approve-button"),
  navButtons: document.querySelectorAll(".nav-button"),
  homeView: document.querySelector("#home-view"),
  reviewView: document.querySelector("#review-view"),
  notificationsView: document.querySelector("#notifications-view"),
  homeReviewCount: document.querySelector("#home-review-count"),
  homePendingCount: document.querySelector("#home-pending-count"),
  homeSentCount: document.querySelector("#home-sent-count"),
  homeActions: document.querySelectorAll("[data-view-target]"),
  notificationCount: document.querySelector("#notification-count"),
  notificationList: document.querySelector("#notification-list"),
};

function setNotice(message, isError = false) {
  elements.notice.textContent = message;
  elements.notice.hidden = !message;
  elements.notice.classList.toggle("is-error", isError);
}

async function api(path, options = {}) {
  const response = await fetch(`${apiBase}${path}`, {
    ...options,
    headers: { Accept: "application/json", ...options.headers },
  });
  if (response.ok) {
    return response.status === 204 ? null : response.json();
  }

  let message = "通信に失敗しました。";
  try {
    const body = await response.json();
    if (typeof body.detail === "string") message = body.detail;
  } catch {
    // A generic error is safer than showing an unexpected response body.
  }
  throw new Error(message);
}

function formatDate(value) {
  return new Intl.DateTimeFormat("ja-JP", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
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
    item.classList.toggle("is-selected", record.id === state.selectedRecordId);
    item.dataset.recordId = record.id;

    const title = document.createElement("strong");
    title.textContent = `${childName(record.child_id)} / ${categoryLabel(record.category)}`;
    const detail = document.createElement("small");
    detail.textContent = `${formatDate(record.occurred_at)} - 信頼度 ${Math.round(record.confidence * 100)}%`;
    item.append(title, detail);
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
  if (!record) return;

  elements.recordMeta.textContent = `${formatDate(record.occurred_at)} / 信頼度 ${Math.round(record.confidence * 100)}%`;
  elements.recordCategory.textContent = categoryLabel(record.category);
  elements.summaryInput.value = record.summary;
  elements.promptInput.value = record.conversation_prompt ?? "";
  renderChildOptions(record);
}

function render() {
  renderRecordList();
  renderDetail();
  renderHome();
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

function renderHome() {
  elements.homeReviewCount.textContent = String(state.records.length);
  elements.homePendingCount.textContent = String(
    state.notifications.filter((notification) => notification.status === "pending").length,
  );
  elements.homeSentCount.textContent = String(
    state.notifications.filter((notification) => notification.status === "sent").length,
  );
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

async function loadApp() {
  setNotice("読み込んでいます...");
  const schools = await api("/schools");
  if (!schools.length) {
    throw new Error("園がまだ登録されていません。先に園を作成してください。");
  }
  state.schoolId = state.schoolId && schools.some((school) => school.id === state.schoolId)
    ? state.schoolId
    : schools[0].id;
  renderSchoolOptions(schools);
  await Promise.all([loadRecords(), loadNotifications()]);
  setNotice("");
}

async function changeView(view) {
  state.activeView = view;
  elements.homeView.hidden = view !== "home";
  elements.reviewView.hidden = view !== "review";
  elements.notificationsView.hidden = view !== "notifications";
  for (const button of elements.navButtons) {
    button.classList.toggle("is-active", button.dataset.view === view);
  }
  if (view === "notifications") {
    try {
      setNotice("読み込んでいます...");
      await loadNotifications();
      setNotice("");
    } catch (error) {
      setNotice(error.message, true);
    }
  }
}

async function submitReview(action) {
  const record = selectedRecord();
  if (!record) return;

  const actionLabel = action === "approve" ? "承認" : "却下";
  if (!window.confirm(`この記録を${actionLabel}しますか？`)) return;

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

elements.schoolSelect.addEventListener("change", async (event) => {
  state.schoolId = event.target.value;
  state.selectedRecordId = null;
  try {
    await Promise.all([loadRecords(), loadNotifications()]);
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
  button.addEventListener("click", async () => {
    await changeView(button.dataset.view);
  });
}

for (const button of elements.homeActions) {
  button.addEventListener("click", async () => {
    await changeView(button.dataset.viewTarget);
  });
}

elements.reviewForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await submitReview("approve");
});

elements.rejectButton.addEventListener("click", async () => {
  await submitReview("reject");
});

loadApp().catch((error) => setNotice(error.message, true));
