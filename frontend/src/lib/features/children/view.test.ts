import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor
} from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiClient } from '$lib/api';
import { AppController } from '$lib/state';
import ChildrenView from './ChildrenView.svelte';
import type { ChildRead } from './types';

const child: ChildRead = {
  id: 'child-1',
  school_id: 'school-1',
  display_name: '山田 はな',
  guardian_line_user_id: null,
  is_active: true,
  archived_at: null,
  created_at: '2026-09-11T00:00:00Z'
};

const json = (value: unknown): Response =>
  new Response(JSON.stringify(value), {
    headers: { 'content-type': 'application/json' }
  });

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('ChildrenView', () => {
  it('非管理者には園児の管理DOMを表示せずAPIも呼ばない', async () => {
    const fetchMock = vi.fn<typeof fetch>();
    render(ChildrenView, {
      api: new ApiClient({ fetch: fetchMock }),
      appController: new AppController(),
      schoolId: 'school-1',
      isSchoolAdmin: false
    });

    expect(
      await screen.findByText('この画面を利用する権限がありません。')
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: '園児を追加' })
    ).not.toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('確認キャンセルでは発行せず、発行したコードを園切替で消す', async () => {
    const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
      const url = String(input);
      if (url.includes('/line/link-invitations/active?')) return json([]);
      if (url.endsWith('/line/link-invitations') && init?.method === 'POST') {
        return json({
          id: 'invitation-1',
          school_id: 'school-1',
          child_id: child.id,
          expires_at: '2026-09-11T12:00:00Z',
          used_at: null,
          revoked_at: null,
          created_at: '2026-09-11T11:00:00Z',
          invite_code: 'one-time-code'
        });
      }
      if (url.includes('/children?')) {
        return json(url.includes('school_id=school-1') ? [child] : []);
      }
      return json({});
    });
    const props = {
      api: new ApiClient({ fetch: fetchMock }),
      appController: new AppController(),
      schoolId: 'school-1',
      isSchoolAdmin: true
    };
    const view = render(ChildrenView, props);

    const issue = await screen.findByRole('button', {
      name: '招待コードを発行'
    });
    await fireEvent.click(issue);
    await fireEvent.click(screen.getByRole('button', { name: 'キャンセル' }));
    expect(
      fetchMock.mock.calls.filter(
        ([url, init]) =>
          String(url).endsWith('/line/link-invitations') &&
          init?.method === 'POST'
      )
    ).toHaveLength(0);

    await fireEvent.click(issue);
    await fireEvent.click(screen.getByRole('button', { name: '実行する' }));
    expect(await screen.findByText('one-time-code')).toBeInTheDocument();

    await view.rerender({ ...props, schoolId: 'school-2' });
    await waitFor(() =>
      expect(screen.queryByText('one-time-code')).not.toBeInTheDocument()
    );
  });

  it('保護者用URLも確認後だけ発行し、園切替で破棄する', async () => {
    const linkedChild = {
      ...child,
      guardian_line_user_id: 'linked-guardian'
    };
    const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
      const url = String(input);
      if (url.includes('/line/link-invitations/active?')) return json([]);
      if (url.includes('/children?')) {
        return json(url.includes('school_id=school-1') ? [linkedChild] : []);
      }
      if (url.endsWith('/guardian-archive-links') && init?.method === 'POST') {
        return json({
          id: 'archive-1',
          school_id: 'school-1',
          child_id: child.id,
          expires_at: '2026-09-12T00:00:00Z',
          revoked_at: null,
          created_at: '2026-09-11T00:00:00Z',
          archive_url: 'https://example.invalid/guardian/#one-time-url'
        });
      }
      return json({});
    });
    const props = {
      api: new ApiClient({ fetch: fetchMock }),
      appController: new AppController(),
      schoolId: 'school-1',
      isSchoolAdmin: true
    };
    const view = render(ChildrenView, props);

    await fireEvent.click(
      await screen.findByRole('button', { name: '保護者用URLを発行' })
    );
    await fireEvent.click(screen.getByRole('button', { name: 'キャンセル' }));
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          String(url).endsWith('/guardian-archive-links') &&
          init?.method === 'POST'
      )
    ).toBe(false);

    await fireEvent.click(
      screen.getByRole('button', { name: '保護者用URLを発行' })
    );
    await fireEvent.click(screen.getByRole('button', { name: '実行する' }));
    expect(
      await screen.findByText('https://example.invalid/guardian/#one-time-url')
    ).toBeInTheDocument();

    await view.rerender({ ...props, schoolId: 'school-2' });
    await waitFor(() =>
      expect(
        screen.queryByText('https://example.invalid/guardian/#one-time-url')
      ).not.toBeInTheDocument()
    );
  });
});
