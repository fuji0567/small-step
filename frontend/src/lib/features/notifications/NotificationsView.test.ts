import { cleanup, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiClient } from '$lib/api';
import { AppController } from '$lib/state';
import NotificationsView from './NotificationsView.svelte';

function responseJson(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    headers: { 'Content-Type': 'application/json' }
  });
}

function failedNotification() {
  return {
    id: 'notification-1',
    record_id: 'record-1',
    channel: 'line',
    scheduled_for: '2026-09-12T08:00:00Z',
    status: 'failed',
    delivery_attempts: 1,
    last_attempt_at: '2026-09-12T08:00:00Z',
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

afterEach(cleanup);

describe('NotificationsView', () => {
  it('試用の承認は配信なしと表示し、管理者にも再送操作を出さない', async () => {
    render(NotificationsView, {
      api: new ApiClient({
        fetch: vi.fn<typeof fetch>().mockResolvedValue(
          responseJson([
            {
              ...failedNotification(),
              status: 'trial',
              delivery_attempts: 0,
              last_attempt_at: null,
              last_failure_kind: null
            }
          ])
        )
      }),
      schoolId: 'school-1',
      isSchoolAdmin: true,
      controller: new AppController()
    });
    expect(
      await screen.findByText('保護者への配信は行いません')
    ).toBeInTheDocument();
    expect(
      screen.getAllByText('試用承認済み（配信なし）').length
    ).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: '再送を予約' })).toBeNull();
    expect(screen.queryByRole('button', { name: '配信を取消' })).toBeNull();
  });
  it('一般の先生には管理操作をDOMへ出さない', async () => {
    const api = new ApiClient({
      fetch: vi
        .fn<typeof fetch>()
        .mockResolvedValue(responseJson([failedNotification()]))
    });

    render(NotificationsView, {
      api,
      schoolId: 'school-1',
      isSchoolAdmin: false,
      controller: new AppController()
    });

    expect(
      await screen.findByText('ブロック遊びを楽しみました。')
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '再送を予約' })).toBeNull();
    expect(screen.queryByRole('button', { name: '配信を取消' })).toBeNull();
  });

  it('先生管理者には失敗通知の再送操作を表示する', async () => {
    const api = new ApiClient({
      fetch: vi
        .fn<typeof fetch>()
        .mockResolvedValue(responseJson([failedNotification()]))
    });

    render(NotificationsView, {
      api,
      schoolId: 'school-1',
      isSchoolAdmin: true,
      controller: new AppController()
    });

    expect(
      await screen.findByRole('button', { name: '再送を予約' })
    ).toHaveAccessibleDescription(
      '送信に失敗した通知を、もう一度送信待ちに戻します。'
    );
  });

  it('先生管理者には送信待ち通知の日時変更と取消を表示する', async () => {
    const api = new ApiClient({
      fetch: vi
        .fn<typeof fetch>()
        .mockResolvedValue(
          responseJson([{ ...failedNotification(), status: 'pending' }])
        )
    });

    render(NotificationsView, {
      api,
      schoolId: 'school-1',
      isSchoolAdmin: true,
      controller: new AppController()
    });

    expect(
      await screen.findByRole('button', { name: '日時を変更' })
    ).toHaveAccessibleDescription(
      'LINE送信が始まる前に限り、配信予定を変更できます。'
    );
    expect(
      screen.getByRole('button', { name: '配信を取消' })
    ).toHaveAccessibleDescription(
      'この通知を送信対象から外します。自動では再開されません。'
    );
  });
});
