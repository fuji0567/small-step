<script lang="ts">
  import { resolve } from '$app/paths';
  import type { ApiClient, RecordCategory, RecordStatus } from '$lib/api';
  import {
    Button,
    ConfirmDialog,
    Loading,
    Notice,
    StatusBadge
  } from '$lib/components';

  import {
    categoryLabel,
    dateBoundaryIso,
    formatDateTime,
    recordDetailPath,
    statusLabel
  } from './format';
  import './records.css';
  import { RecordsService } from './service';
  import type { RecordChild, RecordHistoryFilters, RecordRead } from './types';

  type Props = {
    api: ApiClient;
    schoolId: string | null;
    isSchoolAdmin: boolean;
  };

  let { api, schoolId, isSchoolAdmin }: Props = $props();
  const service = $derived(new RecordsService(api));
  let records = $state.raw<RecordRead[]>([]);
  let children = $state.raw<RecordChild[]>([]);
  let search = $state('');
  let childId = $state('');
  let status = $state<RecordStatus | ''>('');
  let category = $state<RecordCategory | ''>('');
  let occurredFrom = $state('');
  let occurredTo = $state('');
  let loading = $state(false);
  let exporting = $state(false);
  let exportConfirmation = $state(false);
  let errorMessage = $state<string | null>(null);
  let successMessage = $state<string | null>(null);
  let requestVersion = 0;

  const childNames = $derived(
    new Map(children.map((child) => [child.id, child.display_name]))
  );

  function currentFilters(): RecordHistoryFilters {
    return {
      search,
      childId,
      status,
      category,
      occurredFrom: dateBoundaryIso(occurredFrom, 'start'),
      occurredTo: dateBoundaryIso(occurredTo, 'end'),
      limit: 100
    };
  }

  async function load(
    filters: RecordHistoryFilters,
    signal?: AbortSignal
  ): Promise<void> {
    const selectedSchoolId = schoolId;
    const version = ++requestVersion;
    if (!selectedSchoolId) {
      records = [];
      children = [];
      return;
    }
    loading = true;
    errorMessage = null;
    successMessage = null;
    try {
      const [nextChildren, nextRecords] = await Promise.all([
        service.listChildren(selectedSchoolId, signal),
        service.listHistory(selectedSchoolId, filters, signal)
      ]);
      if (version !== requestVersion) return;
      children = nextChildren;
      records = nextRecords;
    } catch (error) {
      if (signal?.aborted || version !== requestVersion) return;
      errorMessage =
        error instanceof Error
          ? error.message
          : '記録履歴を取得できませんでした。';
    } finally {
      if (version === requestVersion) loading = false;
    }
  }

  async function exportCsv(): Promise<void> {
    if (!schoolId || !isSchoolAdmin || records.length === 0) return;
    exporting = true;
    errorMessage = null;
    successMessage = null;
    try {
      const file = await service.exportHistory(schoolId, currentFilters());
      const downloadUrl = URL.createObjectURL(file);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = `small-step-record-history-${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.append(link);
      link.click();
      link.remove();
      globalThis.setTimeout(() => URL.revokeObjectURL(downloadUrl), 0);
      successMessage =
        'CSVをダウンロードしました。園児名と通知内容を含むため、取り扱いに注意してください。';
    } catch (error) {
      errorMessage =
        error instanceof Error
          ? error.message
          : 'CSVをダウンロードできませんでした。';
    } finally {
      exporting = false;
      exportConfirmation = false;
    }
  }

  $effect(() => {
    const currentSchool = schoolId;
    void currentSchool;
    search = '';
    childId = '';
    status = '';
    category = '';
    occurredFrom = '';
    occurredTo = '';
    const controller = new AbortController();
    void load({ limit: 100 }, controller.signal);
    return () => controller.abort();
  });
</script>

<section class="records-page" aria-labelledby="record-history-heading">
  <header class="records-heading">
    <h2 id="record-history-heading">記録履歴</h2>
    <p>レビュー待ち、承認済み、却下、配信済みの日誌を検索できます。</p>
  </header>

  <form
    class="records-card records-form"
    aria-label="記録履歴の検索条件"
    onsubmit={(event) => {
      event.preventDefault();
      void load(currentFilters());
    }}
  >
    <fieldset class="records-filters">
      <legend class="records-legend">検索条件</legend>
      <div class="records-field">
        <label for="history-search">本文</label>
        <input
          id="history-search"
          class="records-control"
          type="search"
          maxlength="120"
          bind:value={search}
        />
      </div>
      <div class="records-field">
        <label for="history-child">園児</label>
        <select id="history-child" class="records-control" bind:value={childId}>
          <option value="">すべて</option>
          {#each children as child (child.id)}
            <option value={child.id}
              >{child.display_name}{child.is_active
                ? ''
                : '（退園済み）'}</option
            >
          {/each}
        </select>
      </div>
      <div class="records-field">
        <label for="history-status">状態</label>
        <select id="history-status" class="records-control" bind:value={status}>
          <option value="">すべて</option>
          <option value="pending_review">レビュー待ち</option>
          <option value="approved">承認済み</option>
          <option value="rejected">却下</option>
          <option value="dispatched">配信済み</option>
        </select>
      </div>
      <div class="records-field">
        <label for="history-category">種別</label>
        <select
          id="history-category"
          class="records-control"
          bind:value={category}
        >
          <option value="">すべて</option>
          <option value="growth">成長記録</option>
          <option value="injury">怪我</option>
        </select>
      </div>
      <div class="records-field">
        <label for="history-from">発生日（開始）</label>
        <input
          id="history-from"
          class="records-control"
          type="date"
          bind:value={occurredFrom}
        />
      </div>
      <div class="records-field">
        <label for="history-to">発生日（終了）</label>
        <input
          id="history-to"
          class="records-control"
          type="date"
          bind:value={occurredTo}
        />
      </div>
    </fieldset>
    <div class="records-actions">
      <Button type="submit" {loading}>検索する</Button>
      {#if isSchoolAdmin}
        <Button
          variant="secondary"
          onclick={() => (exportConfirmation = true)}
          disabled={loading || records.length === 0}>CSVをダウンロード</Button
        >
      {/if}
    </div>
  </form>

  {#if loading}<Loading label="記録履歴を読み込んでいます" />{/if}
  {#if errorMessage}
    <Notice tone="error" title="記録履歴を取得できませんでした"
      ><p>{errorMessage}</p></Notice
    >
  {/if}
  {#if successMessage}
    <Notice tone="success" title="ダウンロードが完了しました"
      ><p>{successMessage}</p></Notice
    >
  {/if}

  <div class="records-toolbar">
    <StatusBadge
      label={`${records.length}件`}
      ariaLabel={`検索条件に一致する記録${records.length}件`}
    />
  </div>

  {#if !loading && !errorMessage && records.length === 0}
    <div class="records-empty"><p>検索条件に一致する記録はありません。</p></div>
  {:else}
    <ul class="records-list">
      {#each records as record (record.id)}
        <li>
          <article class="records-card">
            <div class="records-card-header">
              <h3>
                {record.child_id
                  ? (childNames.get(record.child_id) ??
                    '園児名を確認できません')
                  : '園児未選択'} / {categoryLabel(record.category)}
              </h3>
              <StatusBadge
                label={statusLabel(record.status)}
                tone={record.status === 'rejected'
                  ? 'error'
                  : record.status === 'pending_review'
                    ? 'warning'
                    : 'success'}
              />
            </div>
            <p class="records-meta">
              発生: {formatDateTime(record.occurred_at)}{record.reviewed_at
                ? `・確認: ${formatDateTime(record.reviewed_at)}`
                : ''}
            </p>
            <p>{record.summary}</p>
            {#if record.conversation_prompt}<p>
                会話のきっかけ: {record.conversation_prompt}
              </p>{/if}
            <a class="records-link" href={resolve(recordDetailPath(record.id))}
              >日誌の詳細を開く</a
            >
          </article>
        </li>
      {/each}
    </ul>
  {/if}
</section>

<ConfirmDialog
  bind:open={exportConfirmation}
  title="CSVをダウンロードしますか？"
  description="現在の検索条件に合う記録を保存します。園児名と通知内容を含むため、共有端末や第三者への受け渡しに注意してください。"
  confirmLabel="CSVをダウンロード"
  busy={exporting}
  onConfirm={exportCsv}
  onCancel={() => (exportConfirmation = false)}
/>
