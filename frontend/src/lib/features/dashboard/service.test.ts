import { describe, expect, it, vi } from 'vitest';

import { ApiClient } from '$lib/api';
import { DashboardService, summarizeDashboard } from './service';
import type { DashboardData } from './types';

const json = (value: unknown): Response =>
  new Response(JSON.stringify(value), {
    headers: { 'content-type': 'application/json' }
  });

describe('DashboardService', () => {
  it('一般の先生では管理者専用の招待APIを呼ばない', async () => {
    const fetchMock = vi.fn<typeof fetch>();
    const service = new DashboardService(new ApiClient({ fetch: fetchMock }));

    const invitations = await service.load(
      'invitations',
      'school-1',
      new AbortController().signal,
      false
    );

    expect(invitations).toEqual([]);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('先生管理者では選択園の有効な招待を取得する', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(json([]));
    const service = new DashboardService(new ApiClient({ fetch: fetchMock }));

    await service.load(
      'invitations',
      'school-1',
      new AbortController().signal,
      true
    );

    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      '/api/v1/line/link-invitations/active?school_id=school-1'
    );
  });
});

describe('summarizeDashboard', () => {
  it('対応が必要な状態と招待未発行を数える', () => {
    const data = {
      records: [{ id: 'record-1' }, { id: 'record-2' }],
      notifications: [
        { status: 'pending' },
        { status: 'sent' },
        { status: 'failed' },
        { status: 'waiting_guardian_link' }
      ],
      audioJobs: [
        { status: 'queued' },
        { status: 'processing' },
        { status: 'failed' }
      ],
      children: [
        { id: 'child-1', is_active: true, guardian_line_user_id: null },
        { id: 'child-2', is_active: true, guardian_line_user_id: null },
        {
          id: 'child-3',
          is_active: true,
          guardian_line_user_id: 'line-user'
        },
        { id: 'child-4', is_active: false, guardian_line_user_id: null }
      ],
      invitations: [{ child_id: 'child-1' }]
    } as DashboardData;

    expect(summarizeDashboard(data)).toEqual({
      pendingRecords: 2,
      pendingNotifications: 1,
      sentNotifications: 1,
      notificationWarnings: 2,
      activeAudioJobs: 2,
      failedAudioJobs: 1,
      activeChildren: 3,
      unlinkedChildren: 2,
      activeInvitations: 1,
      invitationsNotIssued: 1
    });
  });
});
