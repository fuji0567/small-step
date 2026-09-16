import type { AuthConfig, AuthenticatedTeacher } from "./types";

export const ACCESS_TOKEN_KEY = "small-step.access-token";
export const REFRESH_TOKEN_KEY = "small-step.recorder-refresh-token";

export interface SessionStorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export interface CredentialStore {
  accessToken(): string | null;
  refreshToken(): string | null;
  save(accessToken: string, refreshToken?: string): void;
  clear(): void;
}

export function createCredentialStore(
  storage: SessionStorageLike,
): CredentialStore {
  return {
    accessToken: () => storage.getItem(ACCESS_TOKEN_KEY),
    refreshToken: () => storage.getItem(REFRESH_TOKEN_KEY),
    save: (accessToken, refreshToken) => {
      storage.setItem(ACCESS_TOKEN_KEY, accessToken);
      if (refreshToken) storage.setItem(REFRESH_TOKEN_KEY, refreshToken);
      else storage.removeItem(REFRESH_TOKEN_KEY);
    },
    clear: () => {
      storage.removeItem(ACCESS_TOKEN_KEY);
      storage.removeItem(REFRESH_TOKEN_KEY);
    },
  };
}

interface PasswordResponse {
  access_token?: unknown;
  refresh_token?: unknown;
}

export interface AuthTokens {
  accessToken: string;
  refreshToken?: string;
}

export class AuthRefreshError extends Error {
  constructor(readonly status: number) {
    super("ログインを更新できませんでした。再度ログインしてください。");
    this.name = "AuthRefreshError";
  }
}

function supabasePasswordUrl(rawUrl: string): string {
  const url = new URL(rawUrl);
  if (
    !["https:", "http:"].includes(url.protocol) ||
    url.username ||
    url.password
  ) {
    throw new Error("Supabaseの接続先設定が不正です。");
  }
  url.pathname = `${url.pathname.replace(/\/$/, "")}/auth/v1/token`;
  url.search = "grant_type=password";
  url.hash = "";
  return url.toString();
}

export async function fetchAuthConfig(
  fetchFn: typeof fetch,
): Promise<AuthConfig> {
  const response = await fetchFn("/api/v1/auth/config", {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error("認証設定を確認できませんでした。");
  return (await response.json()) as AuthConfig;
}

export async function verifyTeacher(
  fetchFn: typeof fetch,
  token: string | null,
): Promise<AuthenticatedTeacher> {
  const headers = new Headers({ Accept: "application/json" });
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetchFn("/api/v1/auth/me", { headers });
  if (!response.ok) throw new Error("ログインの有効期限が切れています。");
  return (await response.json()) as AuthenticatedTeacher;
}

export async function signIn(
  fetchFn: typeof fetch,
  config: AuthConfig,
  email: string,
  password: string,
): Promise<AuthTokens> {
  if (
    config.auth_mode !== "supabase" ||
    !config.supabase_url ||
    !config.supabase_publishable_key
  ) {
    throw new Error("Supabaseの公開設定が不足しています。");
  }
  const response = await fetchFn(supabasePasswordUrl(config.supabase_url), {
    method: "POST",
    headers: {
      apikey: config.supabase_publishable_key,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ email, password }),
  });
  const payload = (await response
    .json()
    .catch(() => null)) as PasswordResponse | null;
  if (!response.ok || typeof payload?.access_token !== "string") {
    throw new Error("ログインできませんでした。入力内容を確認してください。");
  }
  return {
    accessToken: payload.access_token,
    ...(typeof payload.refresh_token === "string"
      ? { refreshToken: payload.refresh_token }
      : {}),
  };
}

export async function refreshSession(
  fetchFn: typeof fetch,
  config: AuthConfig,
  refreshToken: string,
): Promise<AuthTokens> {
  if (
    config.auth_mode !== "supabase" ||
    !config.supabase_url ||
    !config.supabase_publishable_key
  ) {
    throw new Error("Supabaseの公開設定が不足しています。");
  }
  const endpoint = new URL(supabasePasswordUrl(config.supabase_url));
  endpoint.search = "grant_type=refresh_token";
  const response = await fetchFn(endpoint, {
    method: "POST",
    headers: {
      apikey: config.supabase_publishable_key,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  const payload = (await response
    .json()
    .catch(() => null)) as PasswordResponse | null;
  if (!response.ok || typeof payload?.access_token !== "string") {
    throw new AuthRefreshError(response.status);
  }
  return {
    accessToken: payload.access_token,
    ...(typeof payload.refresh_token === "string"
      ? { refreshToken: payload.refresh_token }
      : {}),
  };
}
