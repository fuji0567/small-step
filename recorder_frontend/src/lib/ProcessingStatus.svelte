<script lang="ts">
  import type { ProcessingProgress, StatusIssue } from "./session-status";

  interface Props {
    progress: ProcessingProgress | null;
    issue: StatusIssue | null;
    loading: boolean;
    paused: boolean;
    onRefresh: () => void;
  }

  let { progress, issue, loading, paused, onRefresh }: Props = $props();
  const pending = $derived(
    !progress || ["queued", "processing"].includes(progress.status),
  );
  const labels = {
    queued: "ワーカー待ち",
    processing: "音声を処理しています",
    completed: "処理が完了しました",
    failed: "音声を処理できませんでした",
    expired: "録音の処理期限が切れました",
    discarded: "録音は破棄されました",
  };
</script>

<div aria-live="polite" aria-atomic="true" role="status">
  <h3>
    {issue === "unavailable"
      ? "処理状況を確認できません"
      : progress
        ? labels[progress.status]
        : "処理状況を確認しています"}
  </h3>
  {#if progress && progress.totalSegments > 0}
    <p>
      処理進捗: {progress.processedSegments}/{progress.totalSegments}区間完了
    </p>
  {/if}
</div>

{#if issue === "unavailable"}
  <p class="notice">
    この録音の処理状況を確認できません。録音機能の有効状態とログイン中の先生を確認してください。
  </p>
{:else if pending}
  {#if paused}
    <p class="notice">
      状態の自動更新を一時停止しています。接続して画面に戻ると再開します。受付済みの音声は再送しません。
    </p>
  {:else if issue === "connection"}
    <p class="notice">
      最新の状態を取得できませんでした。接続を確認しながら自動で再試行します。音声を送り直す必要はありません。
    </p>
  {:else}
    <p>状態は約5秒ごとに更新します。サーバーの処理を待っています。</p>
  {/if}
  <button class="secondary" onclick={onRefresh} disabled={loading || paused}>
    状態を再確認する
  </button>
{:else if progress?.status === "completed"}
  {#if progress.recordId}
    {#if progress.incomplete || progress.failedSegments > 0}
      <p class="notice">
        一部の音声を処理できませんでした。記録には抜けがある可能性があります。内容を確認してください。
      </p>
    {/if}
    <p>
      記録は承認待ちとして作成されました。先生が園児と内容を確認し、承認するまで配信されません。
    </p>
    <p>
      <a href={`/teacher/review/${encodeURIComponent(progress.recordId)}/`}>
        作成された記録を確認する
      </a>
    </p>
  {:else}
    <p>
      今回の音声から記録の候補は作成されませんでした。無発話や具体的な出来事がない場合も正常に完了します。
    </p>
  {/if}
{:else if progress?.status === "failed" || progress?.status === "expired"}
  <p class="notice">
    同じ音声の再送や途中再開はできません。接続と稼働状況を確認して録音し直すか、先生用画面から記録を手入力してください。
  </p>
{:else if progress?.status === "discarded"}
  <p>この録音から記録は作成されません。必要な場合は録音し直してください。</p>
{/if}

<p><a href="/teacher/audio-jobs/">先生用の音声処理状況を開く</a></p>
