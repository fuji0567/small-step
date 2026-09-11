<script lang="ts">
  import type { ApiClient } from '$lib/api';
  import {
    Button,
    ConfirmDialog,
    Loading,
    Notice,
    StatusBadge
  } from '$lib/components';
  import type { AppController } from '$lib/state';
  import { onMount } from 'svelte';

  import { AUDIT_ACTION_LABELS, formatDateTime } from './format';
  import './operations.css';
  import { OperationsService } from './service';
  import type { AuditEvent, AuditEventAction, AuditFilters } from './types';

  type Props = {
    api: ApiClient;
    schoolId: string | null;
    isSchoolAdmin: boolean;
    controller: AppController;
  };

  let { api, schoolId, isSchoolAdmin, controller }: Props = $props();
  const service = $derived(new OperationsService(api));
  let events = $state.raw<AuditEvent[]>([]);
  let actionFilter = $state<AuditEventAction | ''>('');
  let occurredFrom = $state('');
  let occurredTo = $state('');
  let loading = $state(false);
  let errorMessage = $state<string | null>(null);
  let noticeMessage = $state<string | null>(null);
  let exportOpen = $state(false);
  let exportBusy = $state(false);
  let requestVersion = 0;

  const actionEntries = Object.entries(AUDIT_ACTION_LABELS) as [
    AuditEventAction,
    string
  ][];

  function filters(): AuditFilters {
    return { action: actionFilter, occurredFrom, occurredTo };
  }

  async function load(signal?: AbortSignal): Promise<void> {
    const selectedSchoolId = schoolId;
    const version = ++requestVersion;
    if (!selectedSchoolId || !isSchoolAdmin) {
      events = [];
      return;
    }
    loading = true;
    errorMessage = null;
    try {
      const value = await service.listAuditEvents(
        selectedSchoolId,
        filters(),
        signal
      );
      if (version === requestVersion) events = value;
    } catch (error) {
      if (signal?.aborted || version !== requestVersion) return;
      errorMessage =
        error instanceof Error
          ? error.message
          : '操作履歴を取得できませんでした。';
    } finally {
      if (version === requestVersion) loading = false;
    }
  }

  function resetFilters(): void {
    actionFilter = '';
    occurredFrom = '';
    occurredTo = '';
    void load();
  }

  async function exportCsv(): Promise<void> {
    const selectedSchoolId = schoolId;
    if (!selectedSchoolId || !isSchoolAdmin || events.length === 0) return;
    exportBusy = true;
    errorMessage = null;
    try {
      const blob = await service.exportAuditEvents(selectedSchoolId, filters());
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `small-step-audit-history-${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.append(link);
      link.click();
      link.remove();
      globalThis.setTimeout(() => URL.revokeObjectURL(url), 0);
      noticeMessage =
        '操作履歴のCSVをダウンロードしました。取り扱いに注意してください。';
      await controller.refresh(['auditEvents']);
    } catch (error) {
      errorMessage =
        error instanceof Error
          ? error.message
          : '操作履歴のCSVをダウンロードできませんでした。';
    } finally {
      exportBusy = false;
    }
  }

  onMount(() => controller.register('auditEvents', () => load()));

  $effect(() => {
    const currentSchool = schoolId;
    void currentSchool;
    const abort = new AbortController();
    void load(abort.signal);
    return () => abort.abort();
  });
</script>

<section class="operations-page" aria-labelledby="audit-heading">
  <header class="operations-heading">
    <h2 id="audit-heading">操作履歴</h2>
    <p>
      園児名、通知文、音声、LINE情報、接続用キーを含まない管理操作だけを表示します。
    </p>
  </header>

  {#if !isSchoolAdmin}
    <Notice tone="error" title="先生管理者専用です"
      ><p>この画面を利用する権限がありません。</p></Notice
    >
  {:else}
    <form
      class="operations-toolbar"
      onsubmit={(event) => {
        event.preventDefault();
        void load();
      }}
    >
      <div class="operations-filters">
        <div class="operations-field">
          <label for="audit-action">操作</label>
          <select id="audit-action" bind:value={actionFilter}>
            <option value="">すべて</option>
            {#each actionEntries as [value, label] (value)}<option {value}
                >{label}</option
              >{/each}
          </select>
        </div>
        <div class="operations-field">
          <label for="audit-from">開始日</label>
          <input id="audit-from" type="date" bind:value={occurredFrom} />
        </div>
        <div class="operations-field">
          <label for="audit-to">終了日</label>
          <input id="audit-to" type="date" bind:value={occurredTo} />
        </div>
      </div>
      <div class="operations-actions">
        <Button type="submit" disabled={loading}>絞り込む</Button>
        <Button variant="tertiary" onclick={resetFilters}>条件をリセット</Button
        >
        <Button
          variant="secondary"
          onclick={() => (exportOpen = true)}
          disabled={events.length === 0}>CSVをダウンロード</Button
        >
        <StatusBadge
          label={`${events.length}件`}
          ariaLabel={`操作履歴${events.length}件`}
        />
      </div>
    </form>

    {#if loading}<Loading label="操作履歴を読み込んでいます" />{/if}
    {#if noticeMessage}<Notice tone="success"><p>{noticeMessage}</p></Notice
      >{/if}
    {#if errorMessage}
      <Notice tone="error" title="操作履歴を処理できませんでした"
        ><p>{errorMessage}</p></Notice
      >
    {:else if !loading && events.length === 0}
      <div class="operations-empty">
        <p>条件に合う操作履歴はありません。</p>
      </div>
    {:else}
      <ul class="operations-list">
        {#each events as event, index (`${event.created_at}:${event.action}:${index}`)}
          <li>
            <article class="operations-card">
              <h3>{AUDIT_ACTION_LABELS[event.action]}</h3>
              <p class="operations-meta">
                {formatDateTime(event.created_at)} / {event.actor_display_name ??
                  'システム'}
              </p>
            </article>
          </li>
        {/each}
      </ul>
    {/if}
  {/if}
</section>

<ConfirmDialog
  bind:open={exportOpen}
  title="CSVをダウンロードしますか？"
  description="現在の条件に合う操作履歴を保存します。実行者の表示名を含むため、園の運用管理以外には共有しないでください。"
  confirmLabel="CSVをダウンロード"
  busy={exportBusy}
  onConfirm={exportCsv}
/>
