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
import TeachersView from './TeachersView.svelte';
import type { TeacherRead } from './types';

const self: TeacherRead = {
  id: 'teacher-self',
  school_id: 'school-1',
  name: '自分',
  email: 'self@example.com',
  role: 'school_admin',
  is_auth_linked: true,
  is_active: true,
  disabled_at: null,
  created_at: '2026-09-11T00:00:00Z'
};
const colleague: TeacherRead = {
  ...self,
  id: 'teacher-other',
  name: '佐藤',
  email: 'other@example.com',
  role: 'teacher'
};
const json = (value: unknown): Response =>
  new Response(JSON.stringify(value), {
    headers: { 'content-type': 'application/json' }
  });

afterEach(cleanup);

describe('TeachersView', () => {
  it('非管理者には登録フォームと先生一覧を表示しない', async () => {
    const fetchMock = vi.fn<typeof fetch>();
    render(TeachersView, {
      api: new ApiClient({ fetch: fetchMock }),
      appController: new AppController(),
      schoolId: 'school-1',
      isSchoolAdmin: false,
      currentTeacherId: 'teacher-self'
    });

    expect(
      await screen.findByText('この画面を利用する権限がありません。')
    ).toBeInTheDocument();
    expect(screen.queryByLabelText('メールアドレス')).not.toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('自分自身の操作を出さず、他の先生の役割変更は確認後だけ送る', async () => {
    const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
      const url = String(input);
      if (url.includes('/teachers?')) return json([self, colleague]);
      if (
        url.endsWith('/teachers/teacher-other/role') &&
        init?.method === 'PATCH'
      ) {
        return json({ ...colleague, role: 'school_admin' });
      }
      return json({});
    });
    render(TeachersView, {
      api: new ApiClient({ fetch: fetchMock }),
      appController: new AppController(),
      schoolId: 'school-1',
      isSchoolAdmin: true,
      currentTeacherId: self.id
    });

    expect(
      await screen.findByText('自分自身の権限変更・利用停止はできません。')
    ).toBeInTheDocument();
    const promote = screen.getByRole('button', { name: '管理者にする' });
    await fireEvent.click(promote);
    await fireEvent.click(screen.getByRole('button', { name: 'キャンセル' }));
    expect(
      fetchMock.mock.calls.some(([, init]) => init?.method === 'PATCH')
    ).toBe(false);

    await fireEvent.click(promote);
    await fireEvent.click(screen.getByRole('button', { name: '実行する' }));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([, init]) => init?.method === 'PATCH')
      ).toBe(true)
    );
  });
});
