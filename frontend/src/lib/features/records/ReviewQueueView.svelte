<script lang="ts">
  import { resolve } from '$app/paths';
  import type { ApiClient } from '$lib/api';
  import { Button, Loading, Notice, StatusBadge } from '$lib/components';

  import { categoryLabel, formatDateTime, recordDetailPath } from './format';
  import './records.css';
  import { RecordsService } from './service';
  import type { RecordChild, RecordRead } from './types';

  type Props = {
    api: ApiClient;
    schoolId: string | null;
  };

  let { api, schoolId }: Props = $props();
  const service = $derived(new RecordsService(api));
  let records = $state.raw<RecordRead[]>([]);
  let children = $state.raw<RecordChild[]>([]);
  let loading = $state(false);
  let errorMessage = $state<string | null>(null);
  let requestVersion = 0;

  const childNames = $derived(
    new Map(children.map((child) => [child.id, child.display_name]))
  );

  async function load(signal?: AbortSignal): Promise<void> {
    const selectedSchoolId = schoolId;
    const version = ++requestVersion;
    if (!selectedSchoolId) {
      records = [];
      children = [];
      return;
    }
    loading = true;
    errorMessage = null;
    try {
      const [nextChildren, nextRecords] = await Promise.all([
        service.listChildren(selectedSchoolId, signal),
        service.listPending(selectedSchoolId, signal)
      ]);
      if (version !== requestVersion) return;
      children = nextChildren;
      records = nextRecords;
    } catch (error) {
      if (signal?.aborted || version !== requestVersion) return;
      errorMessage =
        error instanceof Error ? error.message : '日誌を取得できませんでした。';
    } finally {
      if (version === requestVersion) loading = false;
    }
  }

  $effect(() => {
    const currentSchool = schoolId;
    void currentSchool;
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  });
</script>

<section class="records-page" aria-labelledby="review-queue-heading">
  <header class="records-heading">
    <h2 id="review-queue-heading">レビュー待ち日誌</h2>
    <p>内容を確認してから、保護者への配信を承認してください。</p>
  </header>

  <div class="records-toolbar">
    <StatusBadge
      label={`${records.length}件`}
      ariaLabel={`レビュー待ちの日誌${records.length}件`}
      tone={records.length ? 'warning' : 'neutral'}
    />
    <div class="records-actions">
      <a class="records-link" href={resolve('/teacher-next/review/new/')}
        >手入力で追加</a
      >
      <Button variant="secondary" onclick={() => load()} disabled={loading}>
        再読み込み
      </Button>
    </div>
  </div>

  {#if loading}
    <Loading label="レビュー待ち日誌を読み込んでいます" />
  {/if}
  {#if errorMessage}
    <Notice tone="error" title="日誌を取得できませんでした">
      <p>{errorMessage}</p>
    </Notice>
  {:else if !loading && !schoolId}
    <Notice tone="warning" title="園を選択してください">
      <p>園を選択すると、レビュー待ちの日誌を表示します。</p>
    </Notice>
  {:else if !loading && records.length === 0}
    <div class="records-empty"><p>レビュー待ちの日誌はありません。</p></div>
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
                  : '園児未選択'}
              </h3>
              <StatusBadge label={categoryLabel(record.category)} tone="info" />
            </div>
            <p class="records-meta">
              発生: {formatDateTime(record.occurred_at)}・信頼度
              {Math.round(record.confidence * 100)}%
            </p>
            <p>{record.summary}</p>
            <a class="records-link" href={resolve(recordDetailPath(record.id))}
              >内容を確認する</a
            >
          </article>
        </li>
      {/each}
    </ul>
  {/if}
</section>
