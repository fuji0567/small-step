import { describe, expect, it, vi } from "vitest";

import { RecorderApi, RecorderApiError } from "./api";

describe("RecorderApi", () => {
  it("状態確認を中断でき、API応答をキャッシュしない", async () => {
    const fetchFn = vi.fn(async () => new Response("{}"));
    const api = new RecorderApi({
      fetch: fetchFn as typeof fetch,
      accessToken: () => "token",
    });
    const abort = new AbortController();
    await api.getSession("server/1", abort.signal);
    expect(fetchFn).toHaveBeenCalledWith(
      "/api/v1/recorder/sessions/server%2F1",
      expect.objectContaining({
        signal: expect.any(AbortSignal),
        cache: "no-store",
      }),
    );
  });

  it("通信が30秒応答しなければ中断する", async () => {
    vi.useFakeTimers();
    try {
      const fetchFn = vi.fn(
        (_input: RequestInfo | URL, init?: RequestInit) =>
          new Promise<Response>((_resolve, reject) => {
            init?.signal?.addEventListener("abort", () =>
              reject(new DOMException("Aborted", "AbortError")),
            );
          }),
      );
      const api = new RecorderApi({
        fetch: fetchFn as typeof fetch,
        accessToken: () => "token",
      });
      const result = expect(api.getSession("server-1")).rejects.toMatchObject({
        name: "AbortError",
      });
      await vi.advanceTimersByTimeAsync(30_000);
      await result;
    } finally {
      vi.useRealTimers();
    }
  });

  it("呼び出し元の中断を通信へ伝える", async () => {
    const abort = new AbortController();
    let signal: AbortSignal | null = null;
    const api = new RecorderApi({
      accessToken: () => "token",
      fetch: vi.fn(
        (_input: RequestInfo | URL, init?: RequestInit) =>
          new Promise<Response>((_resolve, reject) => {
            signal = init?.signal ?? null;
            signal?.addEventListener("abort", () =>
              reject(new DOMException("Aborted", "AbortError")),
            );
          }),
      ) as typeof fetch,
    });
    const pending = api.getSession("server-1", abort.signal);
    abort.abort();
    await expect(pending).rejects.toMatchObject({ name: "AbortError" });
  });

  it("資格情報がないと通信せずログインが必要だと識別できる", async () => {
    const fetchFn = vi.fn();
    const api = new RecorderApi({
      fetch: fetchFn as typeof fetch,
      accessToken: () => null,
    });
    await expect(api.getSession("server-1")).rejects.toMatchObject({
      status: 401,
    });
    expect(fetchFn).not.toHaveBeenCalled();
  });

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
