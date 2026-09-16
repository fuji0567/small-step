import { describe, expect, it, vi } from "vitest";

import {
  ACCESS_TOKEN_KEY,
  AuthRefreshError,
  createCredentialStore,
  REFRESH_TOKEN_KEY,
  refreshSession,
} from "./auth";

describe("credential store", () => {
  it("資格情報をrecorder固有を含むsessionStorageキーだけへ保存する", () => {
    const storage = {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    };
    createCredentialStore(storage).save("access", "refresh");

    expect(storage.setItem.mock.calls).toEqual([
      [ACCESS_TOKEN_KEY, "access"],
      [REFRESH_TOKEN_KEY, "refresh"],
    ]);
    expect(ACCESS_TOKEN_KEY).toBe("small-step.access-token");
    expect(REFRESH_TOKEN_KEY).toContain("recorder");
  });
});

describe("refreshSession", () => {
  it("更新トークンを専用エンドポイントへ送り、2xx応答を受け入れる", async () => {
    const fetchFn = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            access_token: "new-access",
            refresh_token: "new-refresh",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
    );
    const tokens = await refreshSession(
      fetchFn as typeof fetch,
      {
        auth_mode: "supabase",
        supabase_url: "https://example.supabase.co",
        supabase_publishable_key: "publishable",
      },
      "old-refresh",
    );

    expect(tokens).toEqual({
      accessToken: "new-access",
      refreshToken: "new-refresh",
    });
    const [url, init] = fetchFn.mock.calls[0] as unknown as [
      RequestInfo | URL,
      RequestInit,
    ];
    expect(String(url)).toContain("grant_type=refresh_token");
    expect(init?.body).toBe(JSON.stringify({ refresh_token: "old-refresh" }));
  });

  it("無効な更新トークンを認証エラーとして識別できる", async () => {
    const fetchFn = vi.fn(async () => new Response(null, { status: 400 }));

    await expect(
      refreshSession(
        fetchFn as typeof fetch,
        {
          auth_mode: "supabase",
          supabase_url: "https://example.supabase.co",
          supabase_publishable_key: "publishable",
        },
        "expired-refresh",
      ),
    ).rejects.toMatchObject<Partial<AuthRefreshError>>({ status: 400 });
  });
});
