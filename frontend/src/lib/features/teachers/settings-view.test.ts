import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor
} from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiClient } from '$lib/api';
import { AppController, type SchoolSummary } from '$lib/state';
import SchoolSettingsView from './SchoolSettingsView.svelte';

const school: SchoolSummary = {
  id: 'school-1',
  name: 'さくら園',
  timezone: 'Asia/Tokyo',
  digest_time: '17:00',
  created_at: '2026-09-11T00:00:00Z'
};
const json = (value: unknown): Response =>
  new Response(JSON.stringify(value), {
    headers: { 'content-type': 'application/json' }
  });

afterEach(cleanup);

describe('SchoolSettingsView', () => {
  it('本番配信はチェックと確認を経て有効になり、キャンセルでは変更しない', async () => {
    const fetchMock = vi.fn<typeof fetch>(async () =>
      json({ ...school, trial_mode: false })
    );
    const onReloadSchools = vi.fn();
    render(SchoolSettingsView, {
      api: new ApiClient({ fetch: fetchMock }),
      appController: new AppController(),
      school: { ...school, trial_mode: true },
      isSchoolAdmin: true,
      onReloadSchools
    });
    const switchButton = screen.getByRole('button', {
      name: '本番モードへ切り替え'
    });
    expect(switchButton).toBeDisabled();
    await fireEvent.click(screen.getByRole('checkbox'));
    expect(switchButton).toBeEnabled();
    await fireEvent.click(switchButton);
    await fireEvent.click(screen.getByRole('button', { name: 'キャンセル' }));
    expect(fetchMock).not.toHaveBeenCalled();
    await fireEvent.click(switchButton);
    await fireEvent.click(
      screen.getByRole('button', { name: '配信を有効にする' })
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain('/schools/school-1/trial-mode');
    expect(JSON.parse(String(init?.body))).toEqual({
      trial_mode: false,
      delivery_confirmed: true
    });
    expect(onReloadSchools).toHaveBeenCalledOnce();
  });
  it('非管理者には配信時刻の入力を表示しない', async () => {
    render(SchoolSettingsView, {
      api: new ApiClient(),
      appController: new AppController(),
      school,
      isSchoolAdmin: false,
      onReloadSchools: vi.fn()
    });

    expect(
      await screen.findByText('この画面を利用する権限がありません。')
    ).toBeInTheDocument();
    expect(
      screen.queryByLabelText('成長記録の既定配信時刻')
    ).not.toBeInTheDocument();
  });

  it('キャンセル時は保存せず、確認後にdigest timeを更新する', async () => {
    const fetchMock = vi.fn<typeof fetch>(async () =>
      json({ ...school, digest_time: '16:30' })
    );
    const onReloadSchools = vi.fn();
    render(SchoolSettingsView, {
      api: new ApiClient({ fetch: fetchMock }),
      appController: new AppController(),
      school,
      isSchoolAdmin: true,
      onReloadSchools
    });

    await fireEvent.input(screen.getByLabelText('成長記録の既定配信時刻'), {
      target: { value: '16:30' }
    });
    await fireEvent.click(
      screen.getByRole('button', { name: '配信時刻を保存' })
    );
    await fireEvent.click(screen.getByRole('button', { name: 'キャンセル' }));
    expect(fetchMock).not.toHaveBeenCalled();

    await fireEvent.click(
      screen.getByRole('button', { name: '配信時刻を保存' })
    );
    const saveButtons = screen.getAllByRole('button', {
      name: '配信時刻を保存'
    });
    await fireEvent.click(saveButtons.at(-1)!);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    expect(onReloadSchools).toHaveBeenCalledOnce();
  });
});
