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
import DevicesView from './DevicesView.svelte';

const json = (value: unknown): Response =>
  new Response(JSON.stringify(value), {
    headers: { 'content-type': 'application/json' }
  });

afterEach(cleanup);

describe('DevicesView', () => {
  it('非管理者には端末登録DOMを表示しない', async () => {
    const fetchMock = vi.fn<typeof fetch>();
    render(DevicesView, {
      api: new ApiClient({ fetch: fetchMock }),
      appController: new AppController(),
      schoolId: 'school-1',
      isSchoolAdmin: false
    });

    expect(
      await screen.findByText('この画面を利用する権限がありません。')
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: '端末を登録' })
    ).not.toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('登録時だけキーを表示し、園切替でDOMから消す', async () => {
    const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
      const url = String(input);
      if (url.includes('/edge-devices?')) return json([]);
      if (url.includes('/teachers?')) {
        return json([{ id: 'teacher-1', name: '佐藤', is_active: true }]);
      }
      if (url.endsWith('/edge-devices') && init?.method === 'POST') {
        return json({
          id: 'device-1',
          school_id: 'school-1',
          teacher_id: 'teacher-1',
          name: '胸元端末',
          is_active: true,
          last_seen_at: null,
          created_at: '2026-09-11T00:00:00Z',
          api_key: 'edge-one-time-key'
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
    const view = render(DevicesView, props);

    await screen.findByRole('option', { name: '佐藤先生' });
    await fireEvent.input(screen.getByLabelText('端末名'), {
      target: { value: '胸元端末' }
    });
    await fireEvent.click(screen.getByRole('button', { name: '端末を登録' }));
    expect(await screen.findByText('edge-one-time-key')).toBeInTheDocument();

    await view.rerender({ ...props, schoolId: 'school-2' });
    await waitFor(() =>
      expect(screen.queryByText('edge-one-time-key')).not.toBeInTheDocument()
    );
  });

  it('鍵の再発行は確認キャンセルでは送らず、確定後だけ実行する', async () => {
    const device = {
      id: 'device-1',
      school_id: 'school-1',
      teacher_id: 'teacher-1',
      name: '胸元端末',
      is_active: true,
      last_seen_at: null,
      created_at: '2026-09-11T00:00:00Z'
    };
    const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
      const url = String(input);
      if (url.includes('/edge-devices?')) return json([device]);
      if (url.includes('/teachers?')) {
        return json([{ id: 'teacher-1', name: '佐藤', is_active: true }]);
      }
      if (
        url.endsWith('/edge-devices/device-1/rotate-key') &&
        init?.method === 'POST'
      ) {
        return json({ ...device, api_key: 'rotated-one-time-key' });
      }
      return json({});
    });
    render(DevicesView, {
      api: new ApiClient({ fetch: fetchMock }),
      appController: new AppController(),
      schoolId: 'school-1',
      isSchoolAdmin: true
    });

    const rotate = await screen.findByRole('button', { name: '鍵を再発行' });
    expect(rotate).toHaveAccessibleDescription(
      '現在の端末キーを無効にし、新しいキーを一度だけ表示します。'
    );
    expect(
      screen.getByRole('button', { name: '端末を無効化' })
    ).toHaveAccessibleDescription(
      'この端末からの新しいデータ送信を停止します。'
    );
    await fireEvent.click(rotate);
    await fireEvent.click(screen.getByRole('button', { name: 'キャンセル' }));
    expect(
      fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')
    ).toBe(false);

    await fireEvent.click(rotate);
    await fireEvent.click(screen.getByRole('button', { name: '実行する' }));
    expect(await screen.findByText('rotated-one-time-key')).toBeInTheDocument();
  });
});
