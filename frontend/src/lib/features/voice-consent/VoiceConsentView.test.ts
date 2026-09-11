import { cleanup, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiClient } from '$lib/api';
import { AppController } from '$lib/state';
import VoiceConsentView from './VoiceConsentView.svelte';

afterEach(cleanup);

describe('VoiceConsentView', () => {
  it('developmentでは設定変更フォームもAPI呼び出しも出さない', () => {
    const fetchMock = vi.fn<typeof fetch>();

    render(VoiceConsentView, {
      api: new ApiClient({ fetch: fetchMock }),
      enabled: false,
      controller: new AppController()
    });

    expect(
      screen.getByText(
        '声紋設定は、Supabaseでログインした先生アカウントでのみ変更できます。'
      )
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '同意を保存' })).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('ログイン済みの先生には未同意状態と保存操作を表示する', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response('null', {
        headers: { 'Content-Type': 'application/json' }
      })
    );

    render(VoiceConsentView, {
      api: new ApiClient({ fetch: fetchMock }),
      enabled: true,
      controller: new AppController()
    });

    expect(await screen.findByText('未同意')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: '同意を保存' })
    ).toBeInTheDocument();
  });
});
