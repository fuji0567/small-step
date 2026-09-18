<script lang="ts">
  import { onMount } from "svelte";
  import { RecorderApiError, type RecorderApi } from "./api";
  import type { RecorderDemo } from "./types";

  let {
    sessionId,
    api,
    onAuthenticationError,
  }: {
    sessionId: string;
    api: Pick<RecorderApi, "getDemo">;
    onAuthenticationError: (error: RecorderApiError) => void;
  } = $props();
  let opened = $state(false);
  let data = $state<RecorderDemo | null>(null);
  let message = $state<string | null>(null);
  let loading = $state(false);
  let remaining = $state(0);
  let generation = 0;
  let request: AbortController | null = null;
  let polling: ReturnType<typeof setTimeout> | null = null;
  const labels: Record<string, string> = {
    transcript: "1. 音声を文字にした結果（話者ラベルは匿名）",
    llm_instruction: "2. LLMに渡した指示",
    llm_input: "2. LLMに渡した文章（匿名化後）",
    llm_output: "3. LLMから実際に返ってきたJSON",
    validation: "4. アプリの形式検証・識別情報の除去",
    candidate: "4. アプリが採用した候補（園児名の除去後）",
    matching: "4. 園児・先生候補の照合結果（先生が確定）",
    decision: "4. アプリの判定",
    failure: "処理に失敗した区間",
  };
  const outcomes: Record<string, string> = {
    waiting: "ワーカーの処理を待っています。完了後に表示します。",
    unavailable: "処理表示を選んでいない録音、または表示期限が切れた録音です。",
    record_created:
      "記録候補を作成しました。園児・担当・本文を先生が確認して確定します。",
    no_record:
      "処理は完了しましたが、この録音から記録候補は作成されませんでした。",
    failed: "処理に失敗したため、記録候補を作成できませんでした。",
  };

  function close() {
    generation++;
    request?.abort();
    request = null;
    if (polling) clearTimeout(polling);
    polling = null;
    data = null;
    opened = false;
    loading = false;
    message = null;
  }

  async function load() {
    if (!opened || request || document.visibilityState !== "visible") return;
    const version = generation;
    const abort = new AbortController();
    request = abort;
    loading = true;
    try {
      const result = await api.getDemo(sessionId, abort.signal);
      if (version !== generation || abort.signal.aborted) return;
      // Rechecking permission must not reset sections the presenter has opened.
      if (
        !data ||
        data.outcome !== result.outcome ||
        data.expires_at !== result.expires_at
      )
        data = result;
      message = null;
      remaining = Math.max(
        0,
        Math.ceil((result.expires_at ?? 0) - Date.now() / 1000),
      );
      if (result.expires_at && !remaining) {
        data = null;
        message = "表示期限が切れたため内容を消しました。";
      } else if (result.outcome !== "unavailable") {
        polling = setTimeout(() => void load(), 5000);
      }
    } catch (error) {
      if (version !== generation) return;
      data = null;
      message =
        "処理内容を表示できませんでした。接続・試用モード・表示期限を確認してください。";
      if (error instanceof RecorderApiError && error.status === 401)
        onAuthenticationError(error);
    } finally {
      if (version === generation) {
        request = null;
        loading = false;
      }
    }
  }

  onMount(() => {
    const visibility = () => {
      if (document.visibilityState !== "visible") close();
    };
    document.addEventListener("visibilitychange", visibility);
    const clock = setInterval(() => {
      if (!data?.expires_at) return;
      remaining = Math.max(0, Math.ceil(data.expires_at - Date.now() / 1000));
      if (!remaining) {
        close();
        message = "表示期限が切れたため内容を消しました。";
      }
    }, 1000);
    return () => {
      clearInterval(clock);
      document.removeEventListener("visibilitychange", visibility);
      close();
    };
  });
</script>

<section class="demo-panel" aria-labelledby="demo-title">
  <h2 id="demo-title">プロコン用：録音から記録候補まで</h2>
  <p>
    実際の入出力とアプリの判定です。AIの内部思考ではありません。録音者本人だけが、処理終了から5分間確認できます。
  </p>
  {#if !opened}
    <button
      type="button"
      onclick={() => {
        opened = true;
        void load();
      }}>直近の録音の処理内容を表示</button
    >
  {:else}
    <button type="button" onclick={close}>内容を隠す</button>
  {/if}
  {#if loading}<p role="status">処理内容を確認しています。</p>{/if}
  {#if message}<p role="status">{message}</p>{/if}
  {#if data}
    <p role="status">{outcomes[data.outcome]}</p>
    {#if data.expires_at}<p>表示終了まで {remaining} 秒</p>{/if}
    {#if data.truncated}<p class="notice">
        表示量の上限に達したため一部を省略しています。処理自体は省略していません。
      </p>{/if}
    {#each data.events as event, index (index)}
      <details open={event.kind === "transcript" || event.kind === "decision"}>
        <summary>{labels[event.kind] ?? "処理結果"}：{event.phase}</summary>
        <pre>{event.text || "発話なし"}</pre>
        {#if event.truncated}<p>この表示は途中までです。</p>{/if}
      </details>
    {/each}
    {#if data.record_id && /^[0-9a-f-]{36}$/i.test(data.record_id)}
      <a href={`/teacher/review/${data.record_id}/`}
        >5. 作成された記録候補を先生が確認する</a
      >
    {/if}
  {/if}
</section>

<style>
  .demo-panel {
    margin-top: 24px;
  }
  details {
    margin-block: 16px;
    border: 2px solid #767676;
    border-radius: 8px;
    padding: 16px;
  }
  summary {
    cursor: pointer;
    font-weight: 700;
  }
  pre {
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    font: inherit;
    margin-bottom: 0;
  }
  summary:focus-visible {
    outline: 3px solid #ffd43d;
    outline-offset: 2px;
    box-shadow: 0 0 0 5px #000;
  }
</style>
