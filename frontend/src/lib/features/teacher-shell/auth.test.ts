import { describe, expect, it, vi } from 'vitest';

import { signInWithSupabasePassword } from './auth';

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
