<script lang="ts">
  import { resolve } from '$app/paths';
  import type { ApiClient } from '$lib/api';
  import { Button, Loading, Notice, StatusBadge } from '$lib/components';
  import type { AppController } from '$lib/state';
  import { untrack } from 'svelte';

  import { DashboardService, summarizeDashboard } from './service';
  import {
    EMPTY_DASHBOARD_DATA,
    type DashboardData,
    type DashboardScope
  } from './types';

  type Props = {
    api: ApiClient;
    schoolId: string | null;
    isSchoolAdmin: boolean;
    controller: AppController;
  };

  let { api, schoolId, isSchoolAdmin, controller }: Props = $props();
  const service = $derived(new DashboardService(api));
  let data = $state.raw<DashboardData>({ ...EMPTY_DASHBOARD_DATA });
  let loadingScopes = $state.raw<ReadonlySet<DashboardScope>>(new Set());
  let errors = $state.raw<Partial<Record<DashboardScope, string>>>({});
  const versions: Record<DashboardScope, number> = {
    records: 0,
    notifications: 0,
    audioJobs: 0,
    children: 0,
    invitations: 0
  };
  const scopes = [
    'records',
    'notifications',
    'audioJobs',
    'children',
    'invitations'
  ] as const satisfies readonly DashboardScope[];

  const summary = $derived(summarizeDashboard(data));
  const loading = $derived(loadingScopes.size > 0);
  const errorCount = $derived(Object.keys(errors).length);
  const attentionCount = $derived(
    summary.pendingRecords +
      summary.notificationWarnings +
      summary.failedAudioJobs +
      (isSchoolAdmin ? summary.invitationsNotIssued : 0)
  );

  function beginLoading(scope: DashboardScope): void {
    loadingScopes = new Set([...loadingScopes, scope]);
    const nextErrors = { ...errors };
    delete nextErrors[scope];
    errors = nextErrors;
  }

  function endLoading(scope: DashboardScope): void {
    const next = new Set(loadingScopes);
    next.delete(scope);
    loadingScopes = next;
  }

  async function loadScope(
    scope: DashboardScope,
    signal = new AbortController().signal
  ): Promise<void> {
    const selectedSchoolId = schoolId;
    const selectedRole = isSchoolAdmin;
    const version = ++versions[scope];
    beginLoading(scope);

    if (!selectedSchoolId) {
      data = { ...data, [scope]: [] };
      endLoading(scope);
      return;
    }

    try {
      const value = await service.load(
        scope,
        selectedSchoolId,
        signal,
        selectedRole
      );
      if (signal.aborted || version !== versions[scope]) return;
      data = { ...data, [scope]: value };
    } catch (error) {
      if (signal.aborted || version !== versions[scope]) return;
      errors = {
        ...errors,
        [scope]:
          error instanceof Error
            ? error.message
            : '状況を取得できませんでした。'
      };
    } finally {
      if (version === versions[scope]) endLoading(scope);
    }
  }

  async function loadAll(signal?: AbortSignal): Promise<void> {
    const controller = signal ? null : new AbortController();
    const requestSignal = signal ?? controller!.signal;
    await Promise.all(scopes.map((scope) => loadScope(scope, requestSignal)));
  }

  $effect(() => {
    const unregister = scopes.map((scope) =>
      controller.register(scope, () => loadScope(scope))
    );
    return () => unregister.forEach((dispose) => dispose());
  });

  $effect(() => {
    const currentSchoolId = schoolId;
    const currentRole = isSchoolAdmin;
    void currentSchoolId;
    void currentRole;
    for (const scope of scopes) versions[scope] += 1;
    data = { ...EMPTY_DASHBOARD_DATA };
    errors = {};
    loadingScopes = new Set();
    const request = new AbortController();
    void untrack(() => loadAll(request.signal));
    return () => request.abort();
  });
</script>

<section class="dashboard" aria-labelledby="dashboard-heading">
  <header class="dashboard__heading">
    <p class="dashboard__eyebrow">今日の概要</p>
    <h2 id="dashboard-heading">今日の状況</h2>
    <p>先生の確認が必要な日誌と、保護者への通知状況を確認できます。</p>
  </header>

  <div class="dashboard__toolbar">
    <StatusBadge
      label={attentionCount === 0 ? '要確認なし' : `要確認 ${attentionCount}件`}
      ariaLabel={attentionCount === 0
        ? '現在、要確認項目はありません'
        : `現在、要確認項目は${attentionCount}件です`}
      tone={attentionCount === 0 ? 'success' : 'warning'}
    />
    <Button
      variant="secondary"
      onclick={() => loadAll()}
      disabled={loading || !schoolId}>再読み込み</Button
    >
  </div>

  {#if loading}
    <Loading label="今日の状況を読み込んでいます" />
  {/if}

  {#if errorCount > 0}
    <Notice tone="error" title="一部の状況を取得できませんでした">
      <p>
        {errorCount}項目を読み込めませんでした。通信状況を確認して再読み込みしてください。
      </p>
    </Notice>
  {:else if !loading && !schoolId}
    <Notice tone="warning" title="園を選択してください">
      <p>表示する園を選択すると、今日の状況を確認できます。</p>
    </Notice>
  {:else if !loading && attentionCount === 0}
    <Notice tone="success" title="今すぐ確認が必要な項目はありません">
      <p>新しい日誌や配信エラーが届くと、この画面に件数が表示されます。</p>
    </Notice>
  {/if}

  <div class="dashboard__grid" aria-live="polite" aria-busy={loading}>
    <a class="dashboard__card" href={resolve('/teacher/review/')}>
      <span class="dashboard__label">レビュー待ち</span>
      <strong>{summary.pendingRecords}<span>件</span></strong>
      <span>先生の確認が必要な日誌です</span>
    </a>

    <a class="dashboard__card" href={resolve('/teacher/notifications/')}>
      <span class="dashboard__label">通知状況</span>
      <strong>{summary.pendingNotifications}<span>件</span></strong>
      <span>送信済み {summary.sentNotifications}件</span>
      {#if summary.notificationWarnings > 0}
        <span class="dashboard__attention"
          >要確認 {summary.notificationWarnings}件</span
        >
      {/if}
    </a>

    <a class="dashboard__card" href={resolve('/teacher/audio-jobs/')}>
      <span class="dashboard__label">音声処理中</span>
      <strong>{summary.activeAudioJobs}<span>件</span></strong>
      <span>安全な処理メタデータだけを表示します</span>
      {#if summary.failedAudioJobs > 0}
        <span class="dashboard__attention"
          >処理失敗 {summary.failedAudioJobs}件</span
        >
      {/if}
    </a>

    <a class="dashboard__card" href={resolve('/teacher/children/')}>
      <span class="dashboard__label">在籍中の園児</span>
      <strong>{summary.activeChildren}<span>人</span></strong>
      <span>保護者LINE未連携 {summary.unlinkedChildren}人</span>
    </a>

    {#if isSchoolAdmin}
      <a class="dashboard__card" href={resolve('/teacher/children/')}>
        <span class="dashboard__label">有効なLINE招待</span>
        <strong>{summary.activeInvitations}<span>件</span></strong>
        <span>招待コード未発行 {summary.invitationsNotIssued}件</span>
        {#if summary.invitationsNotIssued > 0}
          <span class="dashboard__attention">発行が必要です</span>
        {/if}
      </a>
    {/if}
  </div>
</section>

<style>
  .dashboard {
    display: grid;
    gap: var(--ss-space-3);
  }

  .dashboard__heading {
    display: grid;
    gap: var(--ss-space-1);
  }

  .dashboard__heading p,
  .dashboard__heading h2,
  .dashboard__card span,
  .dashboard__card strong {
    margin: 0;
  }

  .dashboard__eyebrow {
    color: var(--ss-color-text-muted);
    font-size: var(--ss-font-size-small);
    font-weight: var(--ss-font-weight-bold);
  }

  .dashboard__toolbar {
    display: flex;
    align-items: center;
    gap: var(--ss-space-2);
  }

  .dashboard__grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 15rem), 1fr));
    gap: var(--ss-space-2);
  }

  .dashboard__card {
    display: grid;
    min-height: 11rem;
    box-sizing: border-box;
    align-content: start;
    gap: var(--ss-space-1);
    border: 2px solid var(--ss-color-border);
    border-radius: var(--ss-radius-large);
    padding: var(--ss-space-3);
    color: var(--ss-color-text);
    background: var(--ss-color-surface);
    text-decoration: none;
  }

  .dashboard__card:hover {
    border-color: var(--ss-color-action-hover);
    color: var(--ss-color-action-hover);
    background: var(--ss-color-action-soft);
  }

  .dashboard__card:focus-visible {
    outline: 4px solid var(--ss-color-focus-inner);
    outline-offset: 0;
    box-shadow: 0 0 0 6px var(--ss-color-focus-outer);
  }

  .dashboard__label {
    font-weight: var(--ss-font-weight-bold);
    text-decoration: underline;
    text-underline-offset: 0.25em;
  }

  .dashboard__card strong {
    font-size: var(--ss-font-size-display);
    line-height: 1.5;
  }

  .dashboard__card strong span {
    margin-left: var(--ss-space-1);
    font-size: var(--ss-font-size-body);
  }

  .dashboard__attention {
    width: fit-content;
    border: 2px solid var(--ss-color-warning-border);
    border-radius: var(--ss-radius-full);
    padding-inline: var(--ss-space-1);
    color: var(--ss-color-warning-text);
    background: var(--ss-color-warning-background);
    font-weight: var(--ss-font-weight-bold);
  }

  @media (max-width: 47.999rem) {
    .dashboard__toolbar {
      align-items: stretch;
      flex-direction: column;
    }

    .dashboard__card {
      min-height: auto;
      padding: var(--ss-space-2);
    }
  }
</style>
