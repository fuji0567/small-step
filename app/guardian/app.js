const archiveTokenStorageKey = "small-step.guardian-archive-token";
const content = document.querySelector("#archive-content");

function archiveToken() {
  const tokenFromUrl = window.location.hash.slice(1);
  if (tokenFromUrl.startsWith("ssa_")) {
    sessionStorage.setItem(archiveTokenStorageKey, tokenFromUrl);
    history.replaceState(null, "", window.location.pathname);
    return tokenFromUrl;
  }
  return sessionStorage.getItem(archiveTokenStorageKey);
}

function formatDate(value) {
  return new Intl.DateTimeFormat("ja-JP", { dateStyle: "long", timeStyle: "short" }).format(new Date(value));
}

function categoryLabel(category) {
  return category === "injury" ? "けがの記録" : "成長の記録";
}

function showError(message) {
  content.replaceChildren();
  const title = document.createElement("h2");
  title.textContent = "このアーカイブは開けません";
  const text = document.createElement("p");
  text.textContent = message;
  content.append(title, text);
}

function renderArchive(archive) {
  content.replaceChildren();
  const title = document.createElement("h2");
  title.textContent = `${archive.child_display_name}さんのお知らせ`;
  const expiration = document.createElement("p");
  expiration.className = "archive-expiration";
  expiration.textContent = `このURLの有効期限: ${formatDate(archive.expires_at)}`;
  content.append(title, expiration);

  if (!archive.notifications.length) {
    const empty = document.createElement("p");
    empty.className = "archive-empty";
    empty.textContent = "送信済みのお知らせはまだありません。";
    content.append(empty);
    return;
  }

  const list = document.createElement("div");
  list.className = "archive-list";
  for (const notification of archive.notifications) {
    const item = document.createElement("article");
    item.className = "archive-item";
    const meta = document.createElement("p");
    meta.className = "archive-meta";
    meta.textContent = `${formatDate(notification.delivered_at)} / ${categoryLabel(notification.category)}`;
    const summary = document.createElement("p");
    summary.className = "archive-summary";
    summary.textContent = notification.summary;
    item.append(meta, summary);
    if (notification.conversation_prompt) {
      const prompt = document.createElement("p");
      prompt.className = "archive-prompt";
      prompt.textContent = notification.conversation_prompt;
      item.append(prompt);
    }
    list.append(item);
  }
  content.append(list);
}

async function loadArchive() {
  const token = archiveToken();
  if (!token) {
    showError("URLが見つかりません。園から届いた最新のURLを開いてください。");
    return;
  }
  try {
    const response = await fetch("/api/v1/guardian/archive", {
      headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
    });
    if (!response.ok) {
      sessionStorage.removeItem(archiveTokenStorageKey);
      throw new Error("URLの有効期限が切れたか、無効になっています。園へ最新のURLをご確認ください。");
    }
    renderArchive(await response.json());
  } catch (error) {
    showError(error.message || "読み込みに失敗しました。時間をおいてもう一度お試しください。");
  }
}

loadArchive();
