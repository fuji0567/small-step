<script lang="ts">
  import type { ApiClient } from '$lib/api';
  import { Button, Loading, Notice, StatusBadge } from '$lib/components';
  import type { AppController } from '$lib/state';
  import { onMount } from 'svelte';

  import {
    audioDescription,
    audioStatusLabel,
    formatDateTime,
    recorderDescription,
    recorderDuration,
    recorderSize,
    recorderStatusLabel,
    recorderTone
  } from './format';
  import './operations.css';
  import { OperationsService } from './service';
  import type {
    CloudAudioJob,
    CloudAudioJobStatus,
    RecorderSession
  } from './types';

  type Props = {
    api: ApiClient;
    schoolId: string | null;
    controller: AppController;
  };

  let { api, schoolId, controller }: Props = $props();
  const service = $derived(new OperationsService(api));
  let jobs = $state.raw<CloudAudioJob[]>([]);
  let recorderSessions = $state.raw<RecorderSession[]>([]);
  let loading = $state(false);
  let errorMessages = $state<string[]>([]);
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
    errorMessages = [];
    if (!selectedSchoolId) {
      jobs = [];
      recorderSessions = [];
      loading = false;
      return;
    }
    jobs = [];
    recorderSessions = [];
    loading = true;

    const results = await Promise.allSettled([
      service.listAudioJobs(selectedSchoolId, signal),
      service.listRecorderSessions(selectedSchoolId, signal)
    ]);
    if (signal?.aborted || version !== requestVersion) return;

    const [audioJobsResult, recorderSessionsResult] = results;
    const nextErrors: string[] = [];
    if (audioJobsResult.status === 'fulfilled') {
      jobs = audioJobsResult.value;
    } else {
      nextErrors.push(
        audioJobsResult.reason instanceof Error
          ? `クラウド音声処理ジョブ: ${audioJobsResult.reason.message}`
          : 'クラウド音声処理ジョブを取得できませんでした。'
      );
    }
    if (recorderSessionsResult.status === 'fulfilled') {
      recorderSessions = recorderSessionsResult.value;
    } else {
      nextErrors.push(
        recorderSessionsResult.reason instanceof Error
          ? `録音セッション: ${recorderSessionsResult.reason.message}`
          : '録音セッションを取得できませんでした。'
      );
    }
    errorMessages = nextErrors;
    loading = false;
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
      label={`${jobs.length + recorderSessions.length}件`}
      ariaLabel={`音声処理${jobs.length + recorderSessions.length}件`}
    />
    <Button variant="secondary" onclick={() => load()} disabled={loading}
      >再読み込み</Button
    >
  </div>

  {#if loading}<Loading label="音声処理状況を読み込んでいます" />{/if}
  {#if errorMessages.length > 0}
    <Notice tone="error" title="音声処理状況を取得できませんでした">
      {#if errorMessages.length === 1}
        <p>一部の一覧を表示しています。</p>
      {:else}
        <p>一覧を表示できませんでした。</p>
      {/if}
      <ul>
        {#each errorMessages as message (message)}<li>{message}</li>{/each}
      </ul>
    </Notice>
  {/if}
  {#if !loading && !schoolId}
    <Notice tone="warning"><p>園を選択してください。</p></Notice>
  {:else if !loading && errorMessages.length === 0 && jobs.length === 0 && recorderSessions.length === 0}
    <div class="operations-empty"><p>音声処理の履歴はまだありません。</p></div>
  {:else if !loading && (jobs.length > 0 || recorderSessions.length > 0)}
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
      {#each recorderSessions as session (session.id)}
        <li>
          <article class="operations-card">
            <div class="operations-card-header">
              <div>
                <h3>録音セッション</h3>
                <p class="operations-meta">
                  受付: {formatDateTime(session.created_at)} / 録音時間:
                  {recorderDuration(session)} / {session.segments
                    .length}セグメント /
                  {recorderSize(session)}
                </p>
              </div>
              <StatusBadge
                label={recorderStatusLabel(session.status)}
                tone={recorderTone(session.status)}
              />
            </div>
            <p>{recorderDescription(session.status)}</p>
            {#if session.processed_segment_count !== undefined}
              <p>
                処理進捗: {session.processed_segment_count}/{session.segments
                  .length}区間完了
              </p>
            {/if}
            {#if session.audio_processing_incomplete}
              <Notice tone="warning" title="一部の音声を処理できませんでした">
                <p>
                  記録には抜けがある可能性があります。内容を確認してください。
                </p>
              </Notice>
            {/if}
            {#if session.record_id}
              <a href={`/teacher/review/${session.record_id}/`}
                >作成された記録を確認する</a
              >
            {/if}
          </article>
        </li>
      {/each}
    </ul>
  {/if}
</section>
