import { cleanup, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import GuardianArchiveView from './GuardianArchiveView.svelte';
import { GUARDIAN_ARCHIVE_TOKEN_STORAGE_KEY } from './token';

const { replaceUrl } = vi.hoisted(() => ({
  replaceUrl: vi.fn((pathname: string, state: Record<string, never>) => {
    void state;
    window.history.replaceState(null, '', pathname);
  })
}));

vi.mock('$app/navigation', () => ({
  replaceState: replaceUrl
}));

function responseJson(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    ...init,
    headers: { 'content-type': 'application/json', ...init.headers }
  });
}

function openArchiveUrl(token: string): void {
  window.history.replaceState(null, '', `/guardian/#${token}`);
}

describe('GuardianArchiveView', () => {
  beforeEach(() => {
    replaceUrl.mockClear();
    window.sessionStorage.clear();
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    window.sessionStorage.clear();
    window.history.replaceState(null, '', '/');
  });

  it('有効なアーカイブを表示し、tokenをURLとDOMから除く', async () => {
    const token = 'ssa_component-secret';
    openArchiveUrl(token);
    const fetchMock = vi.fn<typeof fetch>(async () =>
      responseJson({
        child_display_name: 'あおい',
        expires_at: '2026-09-30T08:00:00Z',
        notifications: [
          {
            delivered_at: '2026-09-11T08:00:00Z',
            category: 'growth',
            summary: 'ブロック遊びを楽しみました。',
            conversation_prompt: 'おうちでも聞いてみてください。'
          }
        ]
      })
    );
    vi.stubGlobal('fetch', fetchMock);

    render(GuardianArchiveView);

    expect(
      await screen.findByRole('heading', { name: 'あおいさんのお知らせ' })
    ).toBeInTheDocument();
    expect(
      screen.getByText('ブロック遊びを楽しみました。')
    ).toBeInTheDocument();
    expect(screen.getByText('成長の記録')).toBeInTheDocument();
    expect(window.location.hash).toBe('');
    expect(replaceUrl).toHaveBeenCalledWith('/guardian/', {});
    expect(
      window.sessionStorage.getItem(GUARDIAN_ARCHIVE_TOKEN_STORAGE_KEY)
    ).toBe(token);
    expect(document.body.innerHTML).not.toContain(token);
    expect(document.body.textContent).not.toContain(token);

    const headers = new Headers(fetchMock.mock.calls[0][1]?.headers);
    expect(headers.get('Authorization')).toBe(`Bearer ${token}`);
  });

  it('配信済みのお知らせがない状態を明示する', async () => {
    openArchiveUrl('ssa_empty-archive');
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>(async () =>
        responseJson({
          child_display_name: 'あおい',
          expires_at: '2026-09-30T08:00:00Z',
          notifications: []
        })
      )
    );

    render(GuardianArchiveView);

    expect(
      await screen.findByText('送信済みのお知らせはまだありません。')
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: 'あおいさんのお知らせ' })
    ).toBeInTheDocument();
  });

  it('無効なURLを表示し、保存tokenもDOMにも残さない', async () => {
    const token = 'ssa_expired-secret';
    openArchiveUrl(token);
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>(async () =>
        responseJson({ detail: `expired ${token}` }, { status: 401 })
      )
    );

    render(GuardianArchiveView);

    expect(
      await screen.findByText(
        'URLの有効期限が切れたか、無効になっています。園へ最新のURLをご確認ください。'
      )
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(
        window.sessionStorage.getItem(GUARDIAN_ARCHIVE_TOKEN_STORAGE_KEY)
      ).toBeNull();
    });
    expect(document.body.innerHTML).not.toContain(token);
    expect(document.body.textContent).not.toContain(token);
  });
});
