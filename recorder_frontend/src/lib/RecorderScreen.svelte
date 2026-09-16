<script lang="ts">
  import type { LocalRecordingSession, RecorderView } from "./types";

  interface Props {
    view: RecorderView;
    elapsedMs?: number;
    segmentCount?: number;
    message?: string | null;
    busy?: boolean;
    finalizing?: boolean;
    cautionConfirmed?: boolean;
    ownedSessions?: LocalRecordingSession[];
    foreignSessionExists?: boolean;
    onConfirmCaution?: () => void;
    onStart?: () => void;
    onPause?: () => void;
    onResume?: () => void;
    onStop?: () => void;
    onSend?: () => void;
    onDiscard?: () => void;
    onShowUnsent?: () => void;
    onBack?: () => void;
    onRetry?: (session: LocalRecordingSession) => void;
    onDiscardSession?: (session: LocalRecordingSession) => void;
  }

  let {
    view,
    elapsedMs = 0,
    segmentCount = 0,
    message = null,
    busy = false,
    finalizing = false,
    cautionConfirmed = false,
    ownedSessions = [],
    foreignSessionExists = false,
    onConfirmCaution = () => undefined,
    onStart = () => undefined,
    onPause = () => undefined,
    onResume = () => undefined,
    onStop = () => undefined,
    onSend = () => undefined,
    onDiscard = () => undefined,
    onShowUnsent = () => undefined,
    onBack = () => undefined,
    onRetry = () => undefined,
    onDiscardSession = () => undefined,
  }: Props = $props();

  function duration(ms: number): string {
    const totalSeconds = Math.floor(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }

  function recordedAt(timestamp: number): string {
    return new Intl.DateTimeFormat("ja-JP", {
      month: "numeric",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(timestamp));
  }
</script>

{#if message}
  <p class="notice" role="status">{message}</p>
{/if}

{#if view === "ready"}
  <section aria-labelledby="ready-title">
    <h2 id="ready-title">録音を始める</h2>
    <p>録音中は画面を点灯したまま、ブラウザを前面に表示してください。</p>
    {#if !cautionConfirmed}
      <div class="caution">
        <h3>録音前の確認</h3>
        <ul>
          <li>録音することを周囲の方へ伝えてください。</li>
          <li>園の共用端末と安全な園内ネットワークを使用してください。</li>
          <li>録音中はほかのアプリへ切り替えないでください。</li>
        </ul>
        <button class="primary" onclick={onConfirmCaution}>確認しました</button>
      </div>
    {:else}
      <button class="record-button" onclick={onStart} disabled={busy}>
        <span aria-hidden="true">●</span> 録音開始
      </button>
    {/if}
    <button class="link-button" onclick={onShowUnsent}
      >未送信の録音を確認</button
    >
  </section>
{:else if view === "recording"}
  <section aria-labelledby="recording-title">
    <p class="state recording-state" id="recording-title">
      <span aria-hidden="true">●</span> 録音中
    </p>
    <p class="timer" aria-label={`録音時間 ${duration(elapsedMs)}`}>
      {duration(elapsedMs)}
    </p>
    <p>画面を点灯したまま、ブラウザを前面に表示してください。</p>
    <div class="actions">
      <button class="secondary" onclick={onPause}>一時停止</button>
      <button class="danger" onclick={onStop}>録音を停止</button>
    </div>
  </section>
{:else if view === "paused"}
  <section aria-labelledby="paused-title">
    <p class="state" id="paused-title">
      <span aria-hidden="true">Ⅱ</span> 一時停止中
    </p>
    <p class="timer" aria-label={`録音時間 ${duration(elapsedMs)}`}>
      {duration(elapsedMs)}
    </p>
    <p>安全を確認してから、明示的に録音を再開してください。</p>
    <div class="actions">
      <button class="primary" onclick={onResume}>録音を再開</button>
      <button class="danger" onclick={onStop}>録音を停止</button>
    </div>
  </section>
{:else if view === "stopped"}
  <section aria-labelledby="stopped-title">
    <h2 id="stopped-title">録音を停止しました</h2>
    <dl>
      <div>
        <dt>録音時間</dt>
        <dd>{duration(elapsedMs)}</dd>
      </div>
      <div>
        <dt>ファイル数</dt>
        <dd>{segmentCount}件</dd>
      </div>
    </dl>
    <p>録音内容の再生機能はありません。送信するか破棄してください。</p>
    <div class="actions">
      <button
        class="primary"
        onclick={onSend}
        disabled={busy || finalizing || segmentCount === 0}>送信する</button
      >
      <button class="danger" onclick={onDiscard} disabled={busy || finalizing}
        >破棄する</button
      >
    </div>
  </section>
{:else if view === "unsent"}
  <section aria-labelledby="unsent-title">
    <h2 id="unsent-title">未送信の録音</h2>
    {#if ownedSessions.length === 0}
      <p>このアカウントの未送信録音はありません。</p>
    {:else}
      <ul class="session-list">
        {#each ownedSessions as session (session.clientSessionId)}
          <li>
            <p><strong>{recordedAt(session.createdAt)}</strong></p>
            <p>
              録音時間 {duration(session.durationMs)}・{session.status ===
              "uploading"
                ? "送信中断"
                : "未送信"}
            </p>
            <div class="actions">
              <button class="primary" onclick={() => onRetry(session)}
                >再送する</button
              >
              <button class="danger" onclick={() => onDiscardSession(session)}
                >破棄する</button
              >
            </div>
          </li>
        {/each}
      </ul>
    {/if}
    {#if foreignSessionExists}
      <p class="notice">
        別の録音者の未送信データがあります。元の録音者がログインしてください。
      </p>
    {/if}
    <button class="secondary" onclick={onBack}>録音待機へ戻る</button>
  </section>
{:else if view === "accepted"}
  <section aria-labelledby="accepted-title">
    <p class="state accepted-state" id="accepted-title">
      <span aria-hidden="true">✓</span> 受付が完了しました
    </p>
    <p>
      録音は端末から削除されました。処理結果は先生用画面で確認してください。
    </p>
    <button class="primary" onclick={onBack}>録音待機へ戻る</button>
  </section>
{/if}
