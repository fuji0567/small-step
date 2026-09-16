import { describe, expect, it, vi } from "vitest";

import { RecorderApi, RecorderApiError } from "./api";

describe("RecorderApi", () => {
  it("全録音APIへBearer認証を付与し、固定パスを使う", async () => {
    const fetchFn = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            id: "server-1",
            client_session_id: "client-1",
            status: "draft",
            segments: [],
            total_duration_ms: 0,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
    );
    const api = new RecorderApi({
      fetch: fetchFn as typeof fetch,
      accessToken: () => "token",
    });

    await api.createSession("client-1");
    const calls = fetchFn.mock.calls as unknown as [
      RequestInfo | URL,
      RequestInit,
    ][];
    const [path, init] = calls[0]!;
    expect(path).toBe("/api/v1/recorder/sessions");
    expect(new Headers(init.headers).get("Authorization")).toBe("Bearer token");
    expect(init.body).toBe(JSON.stringify({ client_session_id: "client-1" }));
  });

  it("401をログイン期限切れとして識別できる", async () => {
    const api = new RecorderApi({
      fetch: vi.fn(
        async () => new Response(null, { status: 401 }),
      ) as typeof fetch,
      accessToken: () => "expired-token",
    });

    await expect(api.getSession("server-1")).rejects.toMatchObject<
      Partial<RecorderApiError>
    >({ status: 401 });
  });
});
