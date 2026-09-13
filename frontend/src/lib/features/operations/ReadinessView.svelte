<script lang="ts">
  import type { ApiClient, RuntimeReadiness } from '$lib/api';
  import { Button, Loading, Notice, StatusBadge } from '$lib/components';
  import type { AppController } from '$lib/state';
  import { onMount } from 'svelte';

  import './operations.css';
  import { OperationsService } from './service';

  type Props = {
    api: ApiClient;
    isSchoolAdmin: boolean;
    controller: AppController;
  };

  let { api, isSchoolAdmin, controller }: Props = $props();
  const service = $derived(new OperationsService(api));
  let readiness = $state<RuntimeReadiness | null>(null);
  let loading = $state(false);
  let errorMessage = $state<string | null>(null);

  async function load(signal?: AbortSignal): Promise<void> {
    if (!isSchoolAdmin) return;
    loading = true;
    errorMessage = null;
    try {
      readiness = await service.readiness(signal);
    } catch (error) {
      if (signal?.aborted) return;
      errorMessage =
        error instanceof Error
          ? error.message
          : '稼働準備の状態を読み込めませんでした。';
    } finally {
      loading = false;
    }
  }

  onMount(() => controller.register('runtimeReadiness', () => load()));

  $effect(() => {
    if (!isSchoolAdmin) return;
    const abort = new AbortController();
    void load(abort.signal);
    return () => abort.abort();
  });
</script>

<section class="operations-page" aria-labelledby="readiness-heading">
  <header class="operations-heading">
    <h2 id="readiness-heading">稼働準備チェック</h2>
    <p>秘密情報を表示せず、運用開始に必要な構成だけを確認します。</p>
  </header>

  {#if !isSchoolAdmin}
    <Notice tone="error" title="先生管理者専用です"
      ><p>この画面を利用する権限がありません。</p></Notice
    >
  {:else}
    <div class="operations-toolbar">
      <StatusBadge
        label={readiness?.status === 'ready' ? '基本準備は完了' : '確認が必要'}
        tone={readiness?.status === 'ready' ? 'success' : 'warning'}
      />
      <Button variant="secondary" onclick={() => load()} disabled={loading}
        >再確認</Button
      >
    </div>
    {#if loading}<Loading label="稼働準備を確認しています" />{/if}
    {#if errorMessage}
      <Notice tone="error" title="稼働準備を確認できませんでした"
        ><p>{errorMessage}</p></Notice
      >
    {:else if readiness}
      <div class="operations-checks">
        <article class="operations-check">
          <h3>データベース接続</h3>
          <StatusBadge
            label={readiness.database_ready ? '確認済み' : '接続を確認'}
            tone={readiness.database_ready ? 'success' : 'error'}
          />
          <p>
            {readiness.database_ready
              ? 'データベースに接続できます。'
              : 'データベースの設定と起動状態を確認してください。'}
          </p>
        </article>
        <article class="operations-check">
          <h3>データベース更新</h3>
          <StatusBadge
            label={readiness.database_migration_current
              ? '最新です'
              : '更新が必要'}
            tone={readiness.database_migration_current ? 'success' : 'error'}
          />
          <p>
            {readiness.database_migration_current
              ? '必要なデータベース更新が適用されています。'
              : '運用開始前にデータベース更新を実行してください。'}
          </p>
        </article>
        <article class="operations-check">
          <h3>音声処理モード</h3>
          <StatusBadge
            label={readiness.cloud_audio_enabled ? 'クラウド処理' : '園内処理'}
            tone={readiness.cloud_audio_enabled ? 'info' : 'success'}
          />
          <p>
            {readiness.cloud_audio_enabled
              ? '短命な音声処理ジョブを使用します。'
              : '音声は園内で処理されます。'}
          </p>
        </article>
        {#if readiness.cloud_audio_enabled}
          <article class="operations-check">
            <h3>一時音声保存先</h3>
            <StatusBadge
              label={readiness.cloud_audio_job_storage_ready
                ? '確認済み'
                : '設定を確認'}
              tone={readiness.cloud_audio_job_storage_ready
                ? 'success'
                : 'error'}
            />
            <p>短命ジョブの保存先が利用できるかを示します。</p>
          </article>
          <article class="operations-check">
            <h3>文章生成AI</h3>
            <StatusBadge
              label={readiness.cloud_audio_llm_configured
                ? '確認済み'
                : '設定を確認'}
              tone={readiness.cloud_audio_llm_configured ? 'success' : 'error'}
            />
            <p>文章生成AIの接続設定が揃っているかを示します。</p>
          </article>
        {/if}
        <article class="operations-check">
          <h3>LINE配信</h3>
          <StatusBadge
            label={readiness.line_delivery_configured
              ? '確認済み'
              : '設定を確認'}
            tone={readiness.line_delivery_configured ? 'success' : 'error'}
          />
          <p>
            {readiness.line_delivery_configured
              ? 'LINE配信に必要な設定が入っています。'
              : '通知を配信する前にLINE設定を確認してください。'}
          </p>
        </article>
      </div>
    {/if}
  {/if}
</section>
