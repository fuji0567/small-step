import { describe, expect, it, vi } from 'vitest';

import { ApiClient } from '$lib/api';
import { filterNotifications, NotificationsService } from './service';
import type { NotificationOverview } from './types';

function notification(
  status: NotificationOverview['status'] = 'failed'
): NotificationOverview {
  return {
    id: 'notification-1',
    record_id: 'record-1',
    channel: 'line',
    scheduled_for: '2026-09-12T08:00:00Z',
    status,
    delivery_attempts: 1,
    last_attempt_at: null,
    last_failure_kind: 'network',
    sent_at: null,
    created_at: '2026-09-11T08:00:00Z',
    child_id: 'child-1',
    child_display_name: 'あおい',
    category: 'growth',
    summary: 'ブロック遊びを楽しみました。',
    notion_synced_at: null,
    notion_page_url: null
  };
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    headers: { 'Content-Type': 'application/json' }
  });
}

describe('NotificationsService', () => {
  it('園と状態で通知を絞り込む', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse([notification()]));
    const service = new NotificationsService(
      new ApiClient({ fetch: fetchMock })
    );

    await service.list('school-1', 'failed');

    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      '/api/v1/notifications?school_id=school-1&notification_status=failed'
    );
  });

  it('管理操作を専用endpointへ送る', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockImplementation(async () => jsonResponse(notification('pending')));
    const service = new NotificationsService(
      new ApiClient({ fetch: fetchMock })
    );

    await service.retry('notification-1');
    await service.cancel('notification-1');
    await service.reschedule('notification-1', '2026-09-13T08:00:00Z');

    expect(fetchMock.mock.calls.map(([path]) => path)).toEqual([
      '/api/v1/notifications/notification-1/retry',
      '/api/v1/notifications/notification-1/cancel',
      '/api/v1/notifications/notification-1/schedule'
    ]);
    expect(fetchMock.mock.calls[2]?.[1]?.body).toBe(
      JSON.stringify({ scheduled_for: '2026-09-13T08:00:00Z' })
    );
  });

  it('園児名と本文を日本語検索できる', () => {
    expect(
      filterNotifications([notification()], { status: '', search: 'ブロック' })
    ).toHaveLength(1);
    expect(
      filterNotifications([notification()], {
        status: 'sent',
        search: 'あおい'
      })
    ).toHaveLength(0);
  });
});
