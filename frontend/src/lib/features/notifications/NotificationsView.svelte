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

  import {
    filterNotifications,
    notificationFailureMessage,
    notificationStatusLabel,
    NotificationsService
  } from './service';
  import './notifications.css';
  import type { NotificationOverview, NotificationStatus } from './types';

  type Action =
    | { kind: 'retry'; notification: NotificationOverview }
    | { kind: 'cancel'; notification: NotificationOverview }
    | {
        kind: 'reschedule';
        notification: NotificationOverview;
        scheduledFor: string;
      };

  type Props = {
    api: ApiClient;
    schoolId: string | null;
    isSchoolAdmin: boolean;
    controller: AppController;
  };

  let { api, schoolId, isSchoolAdmin, controller }: Props = $props();
  const service = $derived(new NotificationsService(api));
  let notifications = $state.raw<NotificationOverview[]>([]);
  let statusFilter = $state<NotificationStatus | ''>('');
  let search = $state('');
  let loading = $state(false);
  let errorMessage = $state<string | null>(null);
  let noticeMessage = $state<string | null>(null);
  let reschedulingId = $state<string | null>(null);
  let scheduledFor = $state('');
  let action = $state<Action | null>(null);
  let confirmationOpen = $state(false);
  let actionBusy = $state(false);
  let requestVersion = 0;

  const filtered = $derived(
    filterNotifications(notifications, { status: '', search })
  );
  const failedCount = $derived(
    notifications.filter((item) => item.status === 'failed').length
  );
  const confirmationTitle = $derived(
    action?.kind === 'retry'
      ? 'LINE通知を再送予約しますか？'
      : action?.kind === 'cancel'
        ? '配信を取消しますか？'
        : '配信日時を変更しますか？'
  );
  const confirmationDescription = $derived(
    action?.kind === 'retry'
      ? '通知を送信待ちへ戻します。LINE送信ワーカーが次の確認時に配信します。'
      : action?.kind === 'cancel'
        ? '送信前の通知を取り消します。取り消した通知は後から自動送信されません。'
        : '指定した未来の日時に配信するよう予約します。送信開始後は変更できません。'
  );

  function formatDateTime(value: string): string {
    return new Intl.DateTimeFormat('ja-JP', {
      dateStyle: 'medium',
      timeStyle: 'short'
    }).format(new Date(value));
  }

  function localDateTime(value: string): string {
    const date = new Date(value);
    if (!Number.isFinite(date.getTime())) return '';
    const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
    return local.toISOString().slice(0, 16);
  }

  function statusTone(
    status: NotificationStatus
  ): 'neutral' | 'info' | 'success' | 'warning' | 'error' {
    if (status === 'sent') return 'success';
    if (status === 'failed') return 'error';
    if (status === 'waiting_guardian_link') return 'warning';
    if (status === 'pending') return 'info';
    return 'neutral';
  }

  async function load(signal?: AbortSignal): Promise<void> {
    const selectedSchoolId = schoolId;
    const selectedStatus = statusFilter;
    const version = ++requestVersion;
    if (!selectedSchoolId) {
      notifications = [];
      return;
    }
    loading = true;
    errorMessage = null;
    try {
      const value = await service.list(
        selectedSchoolId,
        selectedStatus,
        signal
      );
      if (version !== requestVersion) return;
      notifications = value;
      if (!value.some((item) => item.id === reschedulingId)) {
        reschedulingId = null;
      }
    } catch (error) {
      if (signal?.aborted || version !== requestVersion) return;
      errorMessage =
        error instanceof Error ? error.message : '通知を取得できませんでした。';
    } finally {
      if (version === requestVersion) loading = false;
    }
  }

  function beginReschedule(notification: NotificationOverview): void {
    reschedulingId = notification.id;
    scheduledFor = localDateTime(notification.scheduled_for);
  }

  function confirmReschedule(notification: NotificationOverview): void {
    const milliseconds = Date.parse(scheduledFor);
    if (
      !scheduledFor ||
      !Number.isFinite(milliseconds) ||
      milliseconds <= Date.now()
    ) {
      errorMessage = '現在より後の配信日時を入力してください。';
      return;
    }
    action = {
      kind: 'reschedule',
      notification,
      scheduledFor: new Date(milliseconds).toISOString()
    };
    confirmationOpen = true;
  }

  function requestAction(
    kind: 'retry' | 'cancel',
    notification: NotificationOverview
  ): void {
    action = { kind, notification };
    confirmationOpen = true;
  }

  async function executeAction(): Promise<void> {
    if (!action || !isSchoolAdmin) return;
    actionBusy = true;
    errorMessage = null;
    try {
      if (action.kind === 'retry') await service.retry(action.notification.id);
      if (action.kind === 'cancel')
        await service.cancel(action.notification.id);
      if (action.kind === 'reschedule') {
        await service.reschedule(action.notification.id, action.scheduledFor);
        reschedulingId = null;
      }
      noticeMessage =
        action.kind === 'retry'
          ? 'LINE通知を再送予約しました。'
          : action.kind === 'cancel'
            ? '送信前の通知を取り消しました。'
            : '配信予定を変更しました。';
      await controller.refresh(['notifications']);
    } catch (error) {
      errorMessage =
        error instanceof Error ? error.message : '通知を更新できませんでした。';
    } finally {
      actionBusy = false;
      action = null;
    }
  }

  onMount(() => controller.register('notifications', () => load()));

  $effect(() => {
    const currentSchoolId = schoolId;
    const currentStatus = statusFilter;
    void currentSchoolId;
    void currentStatus;
    reschedulingId = null;
    noticeMessage = null;
    const abort = new AbortController();
    void load(abort.signal);
    return () => abort.abort();
  });
</script>

<section class="notifications-page" aria-labelledby="notifications-heading">
  <header class="notifications-heading">
    <h2 id="notifications-heading">通知状況</h2>
    <p>保護者への配信予定と配信結果を確認します。</p>
  </header>

  <div class="notifications-toolbar">
    <div class="notifications-field">
      <label for="notification-status">配信状況</label>
      <select id="notification-status" bind:value={statusFilter}>
        <option value="">すべて</option>
        <option value="pending">送信待ち</option>
        <option value="waiting_guardian_link">保護者LINEの連携待ち</option>
        <option value="sent">送信済み</option>
        <option value="failed">送信失敗</option>
        <option value="cancelled">配信取消</option>
      </select>
    </div>
    <div class="notifications-field">
      <label for="notification-search">園児名・本文で検索</label>
      <input id="notification-search" type="search" bind:value={search} />
    </div>
    <StatusBadge
      label={`${filtered.length}件`}
      ariaLabel={`表示中の通知${filtered.length}件`}
    />
    {#if failedCount > 0}
      <StatusBadge
        label={`！${failedCount}件`}
        ariaLabel={`送信失敗${failedCount}件`}
        tone="error"
      />
    {/if}
  </div>

  {#if loading}<Loading label="通知を読み込んでいます" />{/if}
  {#if noticeMessage}
    <Notice tone="success"><p>{noticeMessage}</p></Notice>
  {/if}
  {#if errorMessage}
    <Notice tone="error" title="通知を処理できませんでした">
      <p>{errorMessage}</p>
    </Notice>
  {:else if !loading && !schoolId}
    <Notice tone="warning"><p>園を選択してください。</p></Notice>
  {:else if !loading && filtered.length === 0}
    <div class="notification-card">
      <p>
        {notifications.length
          ? '条件に合う通知はありません。'
          : '通知はまだありません。'}
      </p>
    </div>
  {:else}
    <ul class="notifications-list">
      {#each filtered as notification (notification.id)}
        <li>
          <article class="notification-card">
            <div class="notification-card-header">
              <div class="notification-content">
                <h3>
                  {notification.child_display_name ?? '園児未選択'} / {notification.category ===
                  'injury'
                    ? 'けがの記録'
                    : '成長の記録'}
                </h3>
                <p>{notification.summary}</p>
              </div>
              <StatusBadge
                label={notificationStatusLabel(notification.status)}
                tone={statusTone(notification.status)}
              />
            </div>
            <p class="notification-meta">
              {notification.sent_at
                ? `送信: ${formatDateTime(notification.sent_at)}`
                : `配信予定: ${formatDateTime(notification.scheduled_for)}`}
              {#if notification.delivery_attempts > 0}
                / 送信試行: {notification.delivery_attempts}回
              {/if}
            </p>
            {#if notification.status === 'failed'}
              <p class="notification-failure">
                {notificationFailureMessage(notification.last_failure_kind)}
              </p>
            {/if}

            {#if isSchoolAdmin}
              <div class="notification-actions">
                {#if notification.status === 'failed'}
                  <Button
                    variant="secondary"
                    onclick={() => requestAction('retry', notification)}
                    >再送を予約</Button
                  >
                {/if}
                {#if notification.status === 'pending' || notification.status === 'waiting_guardian_link'}
                  <Button
                    variant="secondary"
                    onclick={() => beginReschedule(notification)}
                    >日時を変更</Button
                  >
                  <Button
                    variant="danger"
                    onclick={() => requestAction('cancel', notification)}
                    >配信を取消</Button
                  >
                {/if}
              </div>
            {/if}

            {#if isSchoolAdmin && reschedulingId === notification.id}
              <form
                class="notification-reschedule"
                onsubmit={(event) => {
                  event.preventDefault();
                  confirmReschedule(notification);
                }}
              >
                <label for={`notification-schedule-${notification.id}`}
                  >新しい配信日時</label
                >
                <input
                  id={`notification-schedule-${notification.id}`}
                  type="datetime-local"
                  required
                  bind:value={scheduledFor}
                />
                <p>
                  未来の日時を指定してください。LINE送信が始まる前だけ変更できます。
                </p>
                <div class="notification-reschedule-actions">
                  <Button type="submit">この日時で予約</Button>
                  <Button
                    variant="tertiary"
                    onclick={() => (reschedulingId = null)}>変更をやめる</Button
                  >
                </div>
              </form>
            {/if}
          </article>
        </li>
      {/each}
    </ul>
  {/if}
</section>

<ConfirmDialog
  bind:open={confirmationOpen}
  title={confirmationTitle}
  description={confirmationDescription}
  confirmLabel={action?.kind === 'retry'
    ? '再送を予約'
    : action?.kind === 'cancel'
      ? '配信を取消'
      : 'この日時で予約'}
  tone={action?.kind === 'cancel' ? 'danger' : 'default'}
  busy={actionBusy}
  onConfirm={executeAction}
  onCancel={() => (action = null)}
/>
