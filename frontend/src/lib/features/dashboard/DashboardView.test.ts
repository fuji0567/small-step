import { cleanup, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiClient } from '$lib/api';
import { AppController } from '$lib/state';
import DashboardView from './DashboardView.svelte';

const json = (value: unknown, status = 200): Response =>
  new Response(JSON.stringify(value), {
    status,
    headers: { 'content-type': 'application/json' }
  });

const record = {
  id: 'record-1',
  school_id: 'school-1',
  teacher_id: 'teacher-1',
  child_id: 'child-1',
  category: 'growth',
  status: 'pending_review',
  source_event_id: null,
  confidence: 0.9,
  occurred_at: '2026-09-12T00:00:00Z',
  summary: '積み木を片付けました。',
  conversation_prompt: null,
  anonymized_context: null,
  reviewed_at: null,
  created_at: '2026-09-12T00:00:00Z',
  updated_at: '2026-09-12T00:00:00Z'
};

function dashboardFetch(): ReturnType<typeof vi.fn<typeof fetch>> {
  return vi.fn<typeof fetch>(async (input) => {
    const url = String(input);
    if (url.includes('/records?')) return json([record]);
    if (url.includes('/notifications?')) {
      return json([
        { status: 'pending' },
        { status: 'sent' },
        { status: 'failed' }
      ]);
    }
    if (url.includes('/audio-jobs?')) {
      return json([{ status: 'processing' }, { status: 'failed' }]);
    }
    if (url.includes('/children?')) {
      return json([
        {
          id: 'child-1',
          is_active: true,
          guardian_line_user_id: null
        },
        {
          id: 'child-2',
          is_active: true,
          guardian_line_user_id: 'line-user'
        }
      ]);
    }
    if (url.includes('/line/link-invitations/active?')) return json([]);
    return json({}, 404);
  });
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('DashboardView', () => {
  it('選択園の件数と実URLを表示する', async () => {
    const fetchMock = dashboardFetch();

    render(DashboardView, {
      api: new ApiClient({ fetch: fetchMock }),
      schoolId: 'school-1',
      isSchoolAdmin: true,
      controller: new AppController()
    });

    expect(await screen.findByText('招待コード未発行 1件')).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: /レビュー待ち 1件/ })
    ).toHaveAttribute('href', '/teacher/review/');
    expect(screen.getByRole('link', { name: /通知状況 1件/ })).toHaveAttribute(
      'href',
      '/teacher/notifications/'
    );
    expect(
      screen.getByRole('link', { name: /音声処理中 1件/ })
    ).toHaveAttribute('href', '/teacher/audio-jobs/');
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/line/link-invitations/active?school_id=school-1',
      expect.any(Object)
    );
  });

  it('一般の先生には管理者用招待カードをDOMへ出さない', async () => {
    const fetchMock = dashboardFetch();

    render(DashboardView, {
      api: new ApiClient({ fetch: fetchMock }),
      schoolId: 'school-1',
      isSchoolAdmin: false,
      controller: new AppController()
    });

    expect(
      await screen.findByRole('link', { name: /レビュー待ち 1件/ })
    ).toBeInTheDocument();
    expect(screen.queryByText('有効なLINE招待')).toBeNull();
    expect(
      fetchMock.mock.calls.some(([url]) =>
        String(url).includes('/line/link-invitations/active')
      )
    ).toBe(false);
  });

  it('読み込み中・空・一部エラーをaria-liveで伝える', async () => {
    let releaseRecords!: (response: Response) => void;
    const records = new Promise<Response>((resolve) => {
      releaseRecords = resolve;
    });
    const fetchMock = vi.fn<typeof fetch>(async (input) => {
      const url = String(input);
      if (url.includes('/records?')) return records;
      if (url.includes('/notifications?')) {
        return json({ detail: 'private backend detail' }, 500);
      }
      return json([]);
    });

    render(DashboardView, {
      api: new ApiClient({ fetch: fetchMock }),
      schoolId: 'school-1',
      isSchoolAdmin: false,
      controller: new AppController()
    });

    expect(
      screen.getByRole('status', { name: '今日の状況を読み込んでいます' })
    ).toBeInTheDocument();
    releaseRecords(json([]));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('一部の状況を取得できませんでした');
    expect(screen.queryByText('private backend detail')).toBeNull();
    expect(
      screen.getByLabelText('現在、要確認項目はありません')
    ).toBeInTheDocument();
  });

  it('共有controllerの無効化通知で対象件数だけを再取得する', async () => {
    let recordsCallCount = 0;
    const fetchMock = vi.fn<typeof fetch>(async (input) => {
      const url = String(input);
      if (url.includes('/records?')) {
        recordsCallCount += 1;
        return json(
          recordsCallCount === 1 ? [] : [record, { ...record, id: 'record-2' }]
        );
      }
      return json([]);
    });
    const controller = new AppController();

    render(DashboardView, {
      api: new ApiClient({ fetch: fetchMock }),
      schoolId: 'school-1',
      isSchoolAdmin: false,
      controller
    });

    expect(
      await screen.findByText('今すぐ確認が必要な項目はありません')
    ).toBeInTheDocument();
    const requestsBeforeRefresh = fetchMock.mock.calls.length;

    await controller.refresh(['records']);

    await waitFor(() =>
      expect(
        screen.getByRole('link', { name: /レビュー待ち 2件/ })
      ).toBeInTheDocument()
    );
    expect(fetchMock.mock.calls).toHaveLength(requestsBeforeRefresh + 1);
  });

  it('園切替で表示をリセットし新しい園のURLで再取得する', async () => {
    const fetchMock = dashboardFetch();
    const props = {
      api: new ApiClient({ fetch: fetchMock }),
      schoolId: 'school-1',
      isSchoolAdmin: false,
      controller: new AppController()
    };
    const view = render(DashboardView, props);

    await screen.findByRole('link', { name: /レビュー待ち 1件/ });
    await view.rerender({ ...props, schoolId: 'school-2' });

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) =>
          String(url).includes('school_id=school-2')
        )
      ).toBe(true)
    );
  });
});
