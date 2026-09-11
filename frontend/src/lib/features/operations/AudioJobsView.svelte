<script lang="ts">
  import type { ApiClient } from '$lib/api';
  import { Button, Loading, Notice, StatusBadge } from '$lib/components';
  import type { AppController } from '$lib/state';
  import { onMount } from 'svelte';

  import { audioDescription, audioStatusLabel, formatDateTime } from './format';
  import './operations.css';
  import { OperationsService } from './service';
  import type { CloudAudioJob, CloudAudioJobStatus } from './types';

  type Props = {
    api: ApiClient;
    schoolId: string | null;
    controller: AppController;
  };

  let { api, schoolId, controller }: Props = $props();
  const service = $derived(new OperationsService(api));
  let jobs = $state.raw<CloudAudioJob[]>([]);
  let loading = $state(false);
  let errorMessage = $state<string | null>(null);
  let requestVersion = 0;

  function tone(status: CloudAudioJobStatus) {
    if (status === 'completed') return 'success' as const;
    if (status === 'failed') return 'error' as const;
    if (status === 'processing') return 'info' as const;
    if (status === 'expired') return 'warning' as const;
    return 'neutral' as const;
  }

  async function load(signal?: AbortSignal): Promise<void> {
    const selectedSchoolId = schoolId;
    const version = ++requestVersion;
    if (!selectedSchoolId) {
      jobs = [];
      return;
    }
    loading = true;
    errorMessage = null;
    try {
      const value = await service.listAudioJobs(selectedSchoolId, signal);
      if (version === requestVersion) jobs = value;
    } catch (error) {
      if (signal?.aborted || version !== requestVersion) return;
      errorMessage =
        error instanceof Error
          ? error.message
          : '音声処理状況を取得できませんでした。';
    } finally {
      if (version === requestVersion) loading = false;
    }
  }

  onMount(() => controller.register('audioJobs', () => load()));

  $effect(() => {
    const currentSchool = schoolId;
    void currentSchool;
    const abort = new AbortController();
    void load(abort.signal);
    return () => abort.abort();
  });
</script>

<section class="operations-page" aria-labelledby="audio-jobs-heading">
  <header class="operations-heading">
    <h2 id="audio-jobs-heading">音声処理状況</h2>
    <p>音声や文字起こしを表示せず、安全な処理メタデータだけを確認します。</p>
  </header>

  <div class="operations-toolbar">
    <StatusBadge
      label={`${jobs.length}件`}
      ariaLabel={`音声処理ジョブ${jobs.length}件`}
    />
    <Button variant="secondary" onclick={() => load()} disabled={loading}
      >再読み込み</Button
    >
  </div>

  {#if loading}<Loading label="音声処理状況を読み込んでいます" />{/if}
  {#if errorMessage}
    <Notice tone="error" title="音声処理状況を取得できませんでした"
      ><p>{errorMessage}</p></Notice
    >
  {:else if !loading && !schoolId}
    <Notice tone="warning"><p>園を選択してください。</p></Notice>
  {:else if !loading && jobs.length === 0}
    <div class="operations-empty"><p>音声処理の履歴はまだありません。</p></div>
  {:else}
    <ul class="operations-list">
      {#each jobs as job (job.id)}
        <li>
          <article class="operations-card">
            <div class="operations-card-header">
              <div>
                <h3>音声処理ジョブ</h3>
                <p class="operations-meta">
                  受付: {formatDateTime(job.queued_at)} / 処理試行: {job.attempts}回
                </p>
              </div>
              <StatusBadge
                label={audioStatusLabel(job.status)}
                tone={tone(job.status)}
              />
            </div>
            <p>{audioDescription(job.status)}</p>
          </article>
        </li>
      {/each}
    </ul>
  {/if}
</section>
