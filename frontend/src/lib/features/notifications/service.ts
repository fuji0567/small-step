import { ApiClient, ApiInvalidResponseError } from '$lib/api';

import type {
  NotificationFilters,
  NotificationOverview,
  NotificationStatus,
  NotificationUpdate
} from './types';

export class NotificationsService {
  constructor(private readonly api: ApiClient) {}

  async list(
    schoolId: string,
    status: NotificationStatus | '' = '',
    signal?: AbortSignal
  ): Promise<NotificationOverview[]> {
    const params = new URLSearchParams({ school_id: schoolId });
    if (status) params.set('notification_status', status);
    const value = await this.api.requestJson<NotificationOverview[]>(
      `/notifications?${params}`,
      { signal }
    );
    if (!Array.isArray(value)) throw new ApiInvalidResponseError();
    return value;
  }

  retry(id: string): Promise<NotificationUpdate | null> {
    return this.api.requestJson(
      `/notifications/${encodeURIComponent(id)}/retry`,
      {
        method: 'POST'
      }
    );
  }

  cancel(id: string): Promise<NotificationUpdate | null> {
    return this.api.requestJson(
      `/notifications/${encodeURIComponent(id)}/cancel`,
      { method: 'POST' }
    );
  }

  reschedule(
    id: string,
    scheduledFor: string
  ): Promise<NotificationUpdate | null> {
    return this.api.requestJson(
      `/notifications/${encodeURIComponent(id)}/schedule`,
      { method: 'PATCH', json: { scheduled_for: scheduledFor } }
    );
  }
}

export function filterNotifications(
  notifications: readonly NotificationOverview[],
  filters: NotificationFilters
): NotificationOverview[] {
  const search = filters.search.trim().toLocaleLowerCase('ja-JP');
  return notifications.filter((notification) => {
    if (filters.status && notification.status !== filters.status) return false;
    if (!search) return true;
    return [
      notification.child_display_name ?? '園児未選択',
      notification.summary,
      notification.category,
      notification.status
    ]
      .join(' ')
      .toLocaleLowerCase('ja-JP')
      .includes(search);
  });
}

export function notificationStatusLabel(status: NotificationStatus): string {
  return {
    pending: '送信待ち',
    waiting_guardian_link: '保護者LINEの連携待ち',
    sent: '送信済み',
    failed: '送信失敗',
    cancelled: '配信取消'
  }[status];
}

export function notificationFailureMessage(kind: string | null): string {
  return (
    {
      guardian_not_linked: '保護者のLINE連携を確認してください。',
      network: '通信状況を確認して、再送を予約してください。',
      line_unavailable:
        'LINE側の一時的な問題の可能性があります。時間を置いて再送してください。',
      line_rejected: 'LINE設定または保護者の連携状況を確認してください。'
    }[kind ?? ''] ?? '配信状況を確認して、必要に応じて再送してください。'
  );
}
