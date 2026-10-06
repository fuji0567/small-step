<script lang="ts">
  import type { LocalRecordingSession, RecorderView } from "./types";
  import ProcessingStatus from "./ProcessingStatus.svelte";
  import type { ProcessingProgress, StatusIssue } from "./session-status";

  interface Props {
    view: RecorderView;
    elapsedMs?: number;
    segmentCount?: number;
    message?: string | null;
    busy?: boolean;
    finalizing?: boolean;
    continuous?: boolean;
    pendingCount?: number;
    acceptedCount?: number;
    onContinuousChange?: (enabled: boolean) => void;
    onRetryContinuous?: () => void;
    cautionConfirmed?: boolean;
    ownedSessions?: LocalRecordingSession[];
    foreignSessionExists?: boolean;
    processing?: ProcessingProgress | null;
    statusIssue?: StatusIssue | null;
    statusLoading?: boolean;
    statusPaused?: boolean;
    onRefreshStatus?: () => void;
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
    continuous = false,
    pendingCount = 0,
    acceptedCount = 0,
    onContinuousChange = () => undefined,
    onRetryContinuous = () => undefined,
    cautionConfirmed = false,
    ownedSessions = [],
    foreignSessionExists = false,
    processing = null,
    statusIssue = null,
    statusLoading = false,
    statusPaused = false,
    onRefreshStatus = () => undefined,
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
    <p>
      ほかの画面へ切り替えても録音の継続を試みます。iPhone・iPadでは画面ロックやアプリ切り替えでブラウザが録音を中断する場合があります。確実に録音するには画面を開いたままにしてください。
    </p>
    <label>
      <input
        type="checkbox"
        checked={continuous}
        disabled={busy}
        onchange={(event) => onContinuousChange(event.currentTarget.checked)}
      />
      連続録音（60秒ごとに自動送信）
    </label>
    {#if continuous}
      <p>
        開始すると、停止するまで録音と自動送信を続けます（最長12時間）。送信済みの音声は取り消せません。未送信が3区間に達すると一時停止します。
      </p>
      <p>
        記録は先生の確認・承認後に配信します。画面ロック・スリープ中の録音は保証できません。
      </p>
    {/if}
    {#if !cautionConfirmed}
      <div class="caution">
        <h3>録音前の確認</h3>
        <ul>
          <li>録音することを周囲の方へ伝えてください。</li>
          <li>園の共用端末と安全な園内ネットワークを使用してください。</li>
          <li>
            画面を戻したら録音状態と未送信件数を確認してください。マイクが中断された場合は「録音を再開」を押してください。
          </li>
        </ul>
        <button class="primary" onclick={onConfirmCaution}>確認しました</button>
      </div>
    {:else}
      <button class="record-button" onclick={onStart} disabled={busy}>
        <span aria-hidden="true">●</span>
        {continuous ? "連続録音・自動送信を開始" : "録音開始"}
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
    <p>
      ほかの画面へ切り替えても録音の継続を試みます。画面ロック中の録音・自動送信は端末やブラウザによって中断される場合があります。戻ったら録音状態と未送信件数を確認してください。
    </p>
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
      <button
        class="primary"
        onclick={onResume}
        disabled={busy || finalizing || (continuous && pendingCount >= 3)}
        >録音を再開</button
      >
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
    {#if continuous}
      <p>
        最後の短い区間も自動送信します。送信できなかった音声は端末に最大24時間保持します。
      </p>
      <button
        class="secondary"
        onclick={onRetryContinuous}
        disabled={busy || finalizing}>未送信区間の送信を再試行</button
      >
      <button
        class="primary"
        onclick={onBack}
        disabled={busy || finalizing || pendingCount > 0}>録音待機へ戻る</button
      >
      <button
        class="link-button"
        onclick={onShowUnsent}
        disabled={busy || finalizing}>未送信の録音を確認</button
      >
    {:else}
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
    {/if}
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
      録音は端末から削除されました。画面を開いたまま処理結果を確認できます。
    </p>
    <ProcessingStatus
      progress={processing}
      issue={statusIssue}
      loading={statusLoading}
      paused={statusPaused}
      onRefresh={onRefreshStatus}
    />
    <p>
      待機画面へ戻ってもサーバーの処理は続きます。結果は先生用の音声処理状況で確認できます。
    </p>
    <button class="primary" onclick={onBack}>録音待機へ戻る</button>
  </section>
{/if}

{#if continuous && ["recording", "paused", "stopped"].includes(view)}
  <section aria-labelledby="continuous-status-title">
    <h2 id="continuous-status-title">連続録音の送信状況</h2>
    <p>サーバー受付: {acceptedCount}区間 / 未送信: {pendingCount}区間</p>
    <p>
      受付済みの音声は端末から削除します。処理は60秒単位のため、結果には録音時間と処理時間の分だけ遅れがあります。
    </p>
    {#if processing || statusIssue || statusLoading}
      <h3>直近の受付区間</h3>
      <ProcessingStatus
        progress={processing}
        issue={statusIssue}
        loading={statusLoading}
        paused={statusPaused}
        onRefresh={onRefreshStatus}
      />
    {/if}
  </section>
{/if}
