import { describe, expect, it, vi } from 'vitest';

import { ApiClient } from '$lib/api';

import { loadGuardianArchive } from './api';
import {
  consumeGuardianArchiveToken,
  GUARDIAN_ARCHIVE_TOKEN_STORAGE_KEY
} from './token';

function responseJson(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    ...init,
    headers: { 'content-type': 'application/json', ...init.headers }
  });
}

function validArchive() {
  return {
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
  };
}

describe('guardian archive token', () => {
  it('ssa_ tokenを保存し、APIで使う前にhashを消す', async () => {
    const events: string[] = [];
    const setItem = vi.fn(() => events.push('store'));
    const replaceState = vi.fn(() => events.push('remove-hash'));
    const token = consumeGuardianArchiveToken({
      location: { hash: '#ssa_secret-value', pathname: '/guardian/' },
      history: { replaceState },
      sessionStorage: { getItem: vi.fn(), setItem }
    });

    const fetchMock = vi.fn<typeof fetch>(async (_input, init) => {
      events.push('fetch');
      expect(new Headers(init?.headers).get('Authorization')).toBe(
        'Bearer ssa_secret-value'
      );
      return responseJson(validArchive());
    });
    const client = new ApiClient({
      accessToken: () => token,
      fetch: fetchMock
    });
    await client.requestJson('/guardian/archive');

    expect(setItem).toHaveBeenCalledWith(
      GUARDIAN_ARCHIVE_TOKEN_STORAGE_KEY,
      'ssa_secret-value'
    );
    expect(replaceState).toHaveBeenCalledWith(null, '', '/guardian/');
    expect(events).toEqual(['store', 'remove-hash', 'fetch']);
  });

  it('hashにssa_ tokenがない場合はsessionStorageを読む', () => {
    const getItem = vi.fn(() => 'ssa_saved-value');
    const replaceState = vi.fn();

    expect(
      consumeGuardianArchiveToken({
        location: { hash: '', pathname: '/guardian/' },
        history: { replaceState },
        sessionStorage: { getItem, setItem: vi.fn() }
      })
    ).toBe('ssa_saved-value');
    expect(getItem).toHaveBeenCalledWith(GUARDIAN_ARCHIVE_TOKEN_STORAGE_KEY);
    expect(replaceState).not.toHaveBeenCalled();
  });
});

describe('loadGuardianArchive', () => {
  it('配信済みのお知らせだけを表す応答を読み込む', async () => {
    const client = new ApiClient({
      fetch: vi.fn<typeof fetch>(async () => responseJson(validArchive()))
    });
    const storage = { removeItem: vi.fn() };

    await expect(loadGuardianArchive(client, storage)).resolves.toEqual({
      status: 'success',
      archive: validArchive()
    });
    expect(storage.removeItem).not.toHaveBeenCalled();
  });

  it('HTTPエラーではtokenを消し、本文やtokenを結果へ含めない', async () => {
    const client = new ApiClient({
      fetch: vi.fn<typeof fetch>(async () =>
        responseJson({ detail: 'ssa_secret-value is expired' }, { status: 401 })
      )
    });
    const storage = { removeItem: vi.fn() };

    const result = await loadGuardianArchive(client, storage);

    expect(result).toEqual({ status: 'invalid-link' });
    expect(JSON.stringify(result)).not.toContain('ssa_secret-value');
    expect(storage.removeItem).toHaveBeenCalledWith(
      GUARDIAN_ARCHIVE_TOKEN_STORAGE_KEY
    );
  });

  it('通信エラーでは再試行用tokenを消さない', async () => {
    const client = new ApiClient({
      fetch: vi.fn<typeof fetch>(async () => {
        throw new Error('network includes no safe user detail');
      })
    });
    const storage = { removeItem: vi.fn() };

    await expect(loadGuardianArchive(client, storage)).resolves.toEqual({
      status: 'network-error'
    });
    expect(storage.removeItem).not.toHaveBeenCalled();
  });

  it('壊れた成功応答を安全な読み込み失敗として扱う', async () => {
    const client = new ApiClient({
      fetch: vi.fn<typeof fetch>(async () => responseJson({ token: 'ssa_x' }))
    });
    const storage = { removeItem: vi.fn() };

    const result = await loadGuardianArchive(client, storage);

    expect(result).toEqual({ status: 'network-error' });
    expect(JSON.stringify(result)).not.toContain('ssa_x');
    expect(storage.removeItem).not.toHaveBeenCalled();
  });
});
