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
  it('登録後に同じ先生へ招待を送り、送信受付を表示する', async () => {
    const pending = { ...colleague, is_auth_linked: false };
    const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
      const url = String(input);
      if (url.includes('/teachers?')) return json([self, pending]);
      if (url.endsWith('/teachers') && init?.method === 'POST')
        return json(pending);
      return json({ ...pending, invitation_sent_at: '2026-09-18T01:00:00Z' });
    });
    render(TeachersView, {
      api: new ApiClient({ fetch: fetchMock }),
      appController: new AppController(),
      schoolId: 'school-1',
      isSchoolAdmin: true,
      currentTeacherId: self.id,
      invitationsEnabled: true
    });
    await fireEvent.input(screen.getByLabelText('先生名'), {
      target: { value: '佐藤' }
    });
    await fireEvent.input(screen.getByLabelText('メールアドレス'), {
      target: { value: 'other@example.com' }
    });
    await fireEvent.submit(
      screen
        .getByRole('button', { name: '登録して招待を送る' })
        .closest('form')!
    );
    expect(
      await screen.findByText(/先生を登録し、招待メールの送信を受け付けました/)
    ).toBeInTheDocument();
    const posts = fetchMock.mock.calls.filter(
      ([, init]) => init?.method === 'POST'
    );
    expect(posts.map(([url]) => String(url))).toEqual([
      '/api/v1/teachers',
      '/api/v1/teachers/teacher-other/invite'
    ]);
  });

  it('招待失敗でも登録成功を残し、一覧から登録を増やさず再送できる', async () => {
    const pending = { ...colleague, is_auth_linked: false };
    let attempts = 0;
    const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
      const url = String(input);
      if (url.includes('/teachers?')) return json([self, pending]);
      if (url.endsWith('/teachers') && init?.method === 'POST')
        return json(pending);
      if (url.endsWith('/invite') && ++attempts === 1)
        return new Response('{}', { status: 503 });
      return json(pending);
    });
    render(TeachersView, {
      api: new ApiClient({ fetch: fetchMock }),
      appController: new AppController(),
      schoolId: 'school-1',
      isSchoolAdmin: true,
      currentTeacherId: self.id,
      invitationsEnabled: true
    });
    await fireEvent.input(screen.getByLabelText('先生名'), {
      target: { value: '佐藤' }
    });
    await fireEvent.input(screen.getByLabelText('メールアドレス'), {
      target: { value: 'other@example.com' }
    });
    await fireEvent.submit(
      screen
        .getByRole('button', { name: '登録して招待を送る' })
        .closest('form')!
    );
    expect(
      await screen.findByText('先生の登録は完了しています。')
    ).toBeInTheDocument();
    expect(
      await screen.findByText(/招待メールの送信を確認できませんでした/)
    ).toBeInTheDocument();
    await fireEvent.click(
      screen.getByRole('button', { name: '招待メールを送る' })
    );
    expect(
      await screen.findByText(/招待メールの送信を受け付けました。受信した先生/)
    ).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.filter(
        ([url, init]) =>
          String(url).endsWith('/teachers') && init?.method === 'POST'
      )
    ).toHaveLength(1);
  });
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
    expect(promote).toHaveAccessibleDescription(
      '園児・先生・端末・通知などの管理操作を許可します。'
    );
    expect(
      screen.getByRole('button', { name: '利用停止' })
    ).toHaveAccessibleDescription(
      'この先生のログインと担当端末の利用を停止します。履歴は残ります。'
    );
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
