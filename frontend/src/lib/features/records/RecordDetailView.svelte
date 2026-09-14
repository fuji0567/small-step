<script lang="ts">
  import { resolve } from '$app/paths';
  import type { Pathname } from '$app/types';
  import { onMount } from 'svelte';

  import { ApiHttpError, type ApiClient } from '$lib/api';
  import {
    Button,
    ConfirmDialog,
    Loading,
    Notice,
    StatusBadge
  } from '$lib/components';

  import {
    categoryLabel,
    formatDateTime,
    localDateTimeValue,
    recordDetailPath,
    statusLabel
  } from './format';
  import './records.css';
  import { RecordsService } from './service';
  import type { RecordChild, RecordRead, RecordReviewInput } from './types';

  type Props = {
    api: ApiClient;
    schoolId: string | null;
    recordId: string;
    onNavigate: (path: Pathname) => void | Promise<void>;
  };

  let { api, schoolId, recordId, onNavigate }: Props = $props();
  const service = $derived(new RecordsService(api));
  let record = $state<RecordRead | null>(null);
  let children = $state.raw<RecordChild[]>([]);
  let summary = $state('');
  let conversationPrompt = $state('');
  let childId = $state('');
  let scheduledEnabled = $state(false);
  let scheduledFor = $state('');
  let loading = $state(false);
  let saving = $state(false);
  let errorMessage = $state<string | null>(null);
  let errorStatus = $state<number | null>(null);
  let confirmation = $state<'approve' | 'reject' | null>(null);
  let requestVersion = 0;

  const isPending = $derived(record?.status === 'pending_review');
  const dirty = $derived(
    isPending &&
      (summary !== (record?.summary ?? '') ||
        conversationPrompt !== (record?.conversation_prompt ?? '') ||
        childId !== (record?.child_id ?? '') ||
        scheduledEnabled)
  );
  const activeChildren = $derived(children.filter((child) => child.is_active));

  function applyRecord(nextRecord: RecordRead): void {
    record = nextRecord;
    summary = nextRecord.summary;
    conversationPrompt = nextRecord.conversation_prompt ?? '';
    childId = nextRecord.child_id ?? '';
    scheduledEnabled = false;
    scheduledFor = localDateTimeValue();
  }

  function loadError(error: unknown): void {
    errorStatus = error instanceof ApiHttpError ? error.status : null;
    if (errorStatus === 403) {
      errorMessage = 'この日誌を確認する権限がありません。';
    } else if (errorStatus === 404) {
      errorMessage = '指定された日誌は見つかりませんでした。';
    } else {
      errorMessage =
        error instanceof Error ? error.message : '日誌を取得できませんでした。';
    }
  }

  async function load(signal?: AbortSignal): Promise<void> {
    const selectedRecordId = recordId;
    const selectedSchoolId = schoolId;
    const version = ++requestVersion;
    record = null;
    errorMessage = null;
    errorStatus = null;
    if (!selectedSchoolId) return;
    loading = true;
    try {
      const [nextRecord, nextChildren] = await Promise.all([
        service.get(selectedRecordId, signal),
        service.listChildren(selectedSchoolId, signal)
      ]);
      if (version !== requestVersion) return;
      children = nextChildren;
      applyRecord(nextRecord);
    } catch (error) {
      if (signal?.aborted || version !== requestVersion) return;
      loadError(error);
    } finally {
      if (version === requestVersion) loading = false;
    }
  }

  function requestBack(event: MouseEvent): void {
    if (dirty && !globalThis.confirm('編集内容を破棄して一覧へ戻りますか？')) {
      event.preventDefault();
    }
  }

  function reviewInput(): RecordReviewInput | null {
    const normalizedSummary = summary.trim();
    if (!normalizedSummary) {
      errorMessage = '保護者へ伝える内容を入力してください。';
      return null;
    }
    const input: RecordReviewInput = { summary: normalizedSummary };
    if (childId) input.child_id = childId;
    const normalizedPrompt = conversationPrompt.trim();
    if (normalizedPrompt) input.conversation_prompt = normalizedPrompt;
    if (scheduledEnabled) {
      const timestamp = Date.parse(scheduledFor);
      if (!scheduledFor || !Number.isFinite(timestamp)) {
        errorMessage = '配信日時を入力してください。';
        return null;
      }
      input.scheduled_for = new Date(timestamp).toISOString();
    }
    return input;
  }

  async function finishReview(action: 'approve' | 'reject'): Promise<void> {
    if (!record || record.status !== 'pending_review') return;
    const reviewedId = record.id;
    const input = action === 'approve' ? reviewInput() : null;
    if (action === 'approve' && !input) return;
    saving = true;
    errorMessage = null;
    try {
      if (action === 'approve') await service.approve(reviewedId, input!);
      else await service.reject(reviewedId);

      const nextPending = await service.listPending(record.school_id);
      const next = nextPending.find((candidate) => candidate.id !== reviewedId);
      await onNavigate(next ? recordDetailPath(next.id) : '/teacher/review/');
    } catch (error) {
      loadError(error);
      if (error instanceof ApiHttpError && error.status === 409) {
        await load();
      }
    } finally {
      saving = false;
      confirmation = null;
    }
  }

  onMount(() => {
    const warnBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = '';
    };
    globalThis.addEventListener('beforeunload', warnBeforeUnload);
    return () =>
      globalThis.removeEventListener('beforeunload', warnBeforeUnload);
  });

  $effect(() => {
    const currentRecord = recordId;
    const currentSchool = schoolId;
    void currentRecord;
    void currentSchool;
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  });
</script>

<section class="records-page" aria-labelledby="record-detail-heading">
  <header class="records-heading">
    <a
      class="records-link"
      href={resolve('/teacher/review/')}
      onclick={requestBack}>レビュー待ち一覧へ戻る</a
    >
    <h2 id="record-detail-heading">日誌のレビュー</h2>
    <p>日誌IDだけをURLに含め、園児名や本文はURLへ保存しません。</p>
  </header>

  {#if loading}
    <Loading label="日誌を読み込んでいます" />
  {:else if errorMessage && !record}
    <Notice
      tone="error"
      title={errorStatus === 404 ? '日誌が見つかりません' : '日誌を開けません'}
    >
      <p>{errorMessage}</p>
    </Notice>
  {:else if !schoolId}
    <Notice tone="warning" title="園を選択してください">
      <p>園を選択してから日誌を開いてください。</p>
    </Notice>
  {:else if record}
    {#if record.status !== 'pending_review'}
      <Notice tone="warning" title="この日誌は処理済みです">
        <p>
          現在の状態は「{statusLabel(
            record.status
          )}」です。内容は参照できますが、再度承認・却下はできません。
        </p>
      </Notice>
    {/if}
    {#if errorMessage}
      <Notice tone="error" title="操作を完了できませんでした">
        <p>{errorMessage}</p>
      </Notice>
    {/if}

    <article class="records-card">
      <div class="records-card-header">
        <StatusBadge label={categoryLabel(record.category)} tone="info" />
        <StatusBadge
          label={statusLabel(record.status)}
          tone={record.status === 'pending_review' ? 'warning' : 'neutral'}
        />
      </div>
      <p class="records-meta">
        発生: {formatDateTime(record.occurred_at)}・信頼度 {Math.round(
          record.confidence * 100
        )}%
      </p>

      <form class="records-form" onsubmit={(event) => event.preventDefault()}>
        <div class="records-field">
          <label for="record-child">園児</label>
          <select
            id="record-child"
            class="records-control"
            bind:value={childId}
            disabled={!isPending || saving}
          >
            <option value="">未選択</option>
            {#each activeChildren as child (child.id)}
              <option value={child.id}>{child.display_name}</option>
            {/each}
          </select>
        </div>
        <div class="records-field">
          <label for="record-summary">保護者へ伝える内容</label>
          <textarea
            id="record-summary"
            class="records-control"
            maxlength="4000"
            bind:value={summary}
            disabled={!isPending || saving}></textarea>
          <span class="records-support">{summary.length}/4000文字</span>
        </div>
        <div class="records-field">
          <label for="record-prompt">会話のきっかけ（任意）</label>
          <textarea
            id="record-prompt"
            class="records-control"
            maxlength="4000"
            bind:value={conversationPrompt}
            disabled={!isPending || saving}></textarea>
        </div>
        {#if isPending}
          <div class="records-field">
            <label
              ><input
                type="checkbox"
                bind:checked={scheduledEnabled}
                disabled={saving}
              /> 配信日時を指定する</label
            >
            {#if scheduledEnabled}
              <input
                aria-label="配信日時"
                class="records-control"
                type="datetime-local"
                bind:value={scheduledFor}
                disabled={saving}
              />
            {/if}
          </div>
          <div class="records-actions">
            <Button
              onclick={() => (confirmation = 'approve')}
              guide="編集内容を保存し、保護者へのLINE通知を準備します。"
              disabled={saving}>承認する</Button
            >
            <Button
              variant="danger"
              onclick={() => (confirmation = 'reject')}
              guide="確認待ちから外します。保護者には通知されません。"
              disabled={saving}>却下する</Button
            >
          </div>
        {/if}
      </form>
    </article>
  {/if}
</section>

<ConfirmDialog
  open={confirmation !== null}
  title={confirmation === 'reject'
    ? '日誌を却下しますか？'
    : '日誌を承認しますか？'}
  description={confirmation === 'reject'
    ? 'この日誌はレビュー待ちの一覧から外れます。'
    : '編集内容を保存し、保護者への通知を準備します。'}
  confirmLabel={confirmation === 'reject' ? '却下する' : '承認する'}
  tone={confirmation === 'reject' ? 'danger' : 'default'}
  busy={saving}
  onConfirm={() => finishReview(confirmation ?? 'approve')}
  onCancel={() => (confirmation = null)}
/>
