import type { SupabasePasswordResponse } from './types';

const AUTH_TIMEOUT_MS = 15_000;
const LOGIN_ERROR_MESSAGE =
  'ログインできませんでした。メールアドレスとパスワードを確認してください。';

export interface PasswordSignInOptions {
  email: string;
  password: string;
  supabaseUrl: string;
  publishableKey: string;
  fetch: typeof fetch;
  timeoutMs?: number;
}

function passwordEndpoint(supabaseUrl: string): string {
  const base = new URL(supabaseUrl);
  if (
    !['http:', 'https:'].includes(base.protocol) ||
    base.username ||
    base.password
  ) {
    throw new Error('Supabaseの接続先設定が不正です。');
  }
  base.pathname = `${base.pathname.replace(/\/$/, '')}/auth/v1/token`;
  base.search = 'grant_type=password';
  base.hash = '';
  return base.toString();
}

export async function signInWithSupabasePassword({
  email,
  password,
  supabaseUrl,
  publishableKey,
  fetch: fetchFn,
  timeoutMs = AUTH_TIMEOUT_MS
}: PasswordSignInOptions): Promise<string> {
  const controller = new AbortController();
  const timeout = globalThis.setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetchFn(passwordEndpoint(supabaseUrl), {
      method: 'POST',
      headers: {
        apikey: publishableKey,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ email, password }),
      signal: controller.signal
    });
    const payload = (await response
      .json()
      .catch(() => null)) as SupabasePasswordResponse | null;
    if (!response.ok || typeof payload?.access_token !== 'string') {
      throw new Error(LOGIN_ERROR_MESSAGE);
    }
    return payload.access_token;
  } catch (error) {
    if (error instanceof Error && error.message === LOGIN_ERROR_MESSAGE) {
      throw error;
    }
    if (controller.signal.aborted) {
      throw new Error('ログイン処理が時間内に完了しませんでした。', {
        cause: error
      });
    }
    throw new Error('ログイン先へ接続できませんでした。', { cause: error });
  } finally {
    globalThis.clearTimeout(timeout);
  }
}
