import { describe, expect, it, vi } from 'vitest';

import {
  signInWithSupabasePassword,
  setInvitedPassword,
  takeInvitationToken
} from './auth';

describe('signInWithSupabasePassword', () => {
  it('Supabaseの公開設定だけを使い、アクセストークンを返す', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ access_token: 'jwt-value' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      })
    );

    await expect(
      signInWithSupabasePassword({
        email: 'teacher@example.com',
        password: 'secret',
        supabaseUrl: 'https://example.supabase.co/',
        publishableKey: 'public-key',
        fetch: fetchMock
      })
    ).resolves.toBe('jwt-value');

    expect(fetchMock).toHaveBeenCalledWith(
      'https://example.supabase.co/auth/v1/token?grant_type=password',
      expect.objectContaining({
        method: 'POST',
        headers: {
          apikey: 'public-key',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          email: 'teacher@example.com',
          password: 'secret'
        })
      })
    );
  });

  it('認証サーバーの詳細なエラー本文を画面へ伝播しない', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(
        new Response(
          JSON.stringify({ error_description: 'internal account detail' }),
          { status: 400, headers: { 'Content-Type': 'application/json' } }
        )
      );

    await expect(
      signInWithSupabasePassword({
        email: 'teacher@example.com',
        password: 'wrong',
        supabaseUrl: 'https://example.supabase.co',
        publishableKey: 'public-key',
        fetch: fetchMock
      })
    ).rejects.toThrow(
      'ログインできませんでした。メールアドレスとパスワードを確認してください。'
    );
  });
});

describe('招待の受け入れ', () => {
  it('招待トークンだけを取り出し、URLから資格情報を直ちに除く', () => {
    window.history.replaceState(
      null,
      '',
      '/teacher/#type=invite&access_token=invitation-token&refresh_token=private-refresh'
    );
    expect(takeInvitationToken()).toBe('invitation-token');
    expect(window.location.hash).toBe('');
    window.history.replaceState(
      null,
      '',
      '/teacher/#type=other&access_token=unexpected'
    );
    expect(takeInvitationToken()).toBeNull();
    expect(window.location.hash).toBe('');
  });

  it('公開キーと本人トークンだけでSupabaseへパスワードを送る', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response('{}'));
    await setInvitedPassword({
      token: 'invite-jwt',
      password: 'new-password',
      supabaseUrl: 'https://example.supabase.co/',
      publishableKey: 'public-key',
      fetch: fetchMock
    });
    expect(fetchMock).toHaveBeenCalledWith(
      'https://example.supabase.co/auth/v1/user',
      expect.objectContaining({
        method: 'PUT',
        headers: {
          apikey: 'public-key',
          Authorization: 'Bearer invite-jwt',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ password: 'new-password' })
      })
    );
  });

  it('パスワード設定の応答本文をエラーへ流さない', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(
        new Response('PRIVATE_PROVIDER_DETAIL', { status: 401 })
      );
    await expect(
      setInvitedPassword({
        token: 'expired',
        password: 'new-password',
        supabaseUrl: 'https://example.supabase.co/',
        publishableKey: 'public-key',
        fetch: fetchMock
      })
    ).rejects.toThrow('招待の期限');
  });
});
