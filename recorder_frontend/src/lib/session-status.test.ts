import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RecorderApiError, type RecorderApi } from "./api";
import { AuthRefreshError } from "./auth";
import {
  processingProgress,
  readSessionStatus,
  SessionStatusMonitor,
} from "./session-status";
import type { ServerRecordingSession } from "./types";

const recordId = "11111111-1111-4111-8111-111111111111";

function session(
  status = "queued",
  changes: Partial<ServerRecordingSession> = {},
): ServerRecordingSession {
  return {
    id: "session-1",
    client_session_id: "client-1",
    status,
    segments: [0, 1].map((sequence) => ({
      sequence,
      duration_ms: 60_000,
      size_bytes: 1_000,
      sha256: "not-for-display",
      media_type: "audio/webm",
    })),
    total_duration_ms: 120_000,
    processed_segment_count: 0,
    failed_segment_count: 0,
    ...changes,
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => (resolve = done));
  return { promise, resolve };
}

describe("readSessionStatus", () => {
  function setup() {
    const getSession = vi.fn().mockResolvedValue(session());
    const refreshAuthentication = vi.fn(async () => undefined);
    const abort = new AbortController();
    const options = {
      api: { getSession } as unknown as RecorderApi,
      id: "session-1",
      signal: abort.signal,
      isCurrent: () => true,
      refreshAuthentication,
    };
    return { options, getSession, refreshAuthentication, abort };
  }

  it("有効な認証ならトークンを毎回更新しない", async () => {
    const handlers = setup();
    await readSessionStatus(handlers.options);
    expect(handlers.getSession).toHaveBeenCalledOnce();
    expect(handlers.refreshAuthentication).not.toHaveBeenCalled();
  });

  it("401で1回だけ認証を更新しGETをやり直す", async () => {
    const handlers = setup();
    handlers.getSession.mockRejectedValueOnce(
      new RecorderApiError(401, "期限切れ"),
    );
    await readSessionStatus(handlers.options);
    expect(handlers.getSession).toHaveBeenCalledTimes(2);
    expect(handlers.refreshAuthentication).toHaveBeenCalledOnce();
  });

  it("更新後も401なら繰り返さずログインに戻せる", async () => {
    const handlers = setup();
    handlers.getSession.mockRejectedValue(
      new RecorderApiError(401, "期限切れ"),
    );
    await expect(readSessionStatus(handlers.options)).rejects.toMatchObject({
      status: 401,
    });
    expect(handlers.getSession).toHaveBeenCalledTimes(2);
    expect(handlers.refreshAuthentication).toHaveBeenCalledOnce();
  });

  it.each([400, 401])(
    "認証更新のHTTP %sをログイン必須として扱う",
    async (status) => {
      const handlers = setup();
      handlers.getSession.mockRejectedValue(
        new RecorderApiError(401, "期限切れ"),
      );
      handlers.refreshAuthentication.mockRejectedValue(
        new AuthRefreshError(status),
      );
      await expect(readSessionStatus(handlers.options)).rejects.toMatchObject({
        status: 401,
      });
      expect(handlers.getSession).toHaveBeenCalledOnce();
    },
  );

  it("通信失敗や403では認証更新を行わない", async () => {
    const handlers = setup();
    for (const error of [
      new Error("通信失敗"),
      new RecorderApiError(403, "権限なし"),
    ]) {
      handlers.getSession.mockRejectedValueOnce(error);
      await expect(readSessionStatus(handlers.options)).rejects.toBe(error);
    }
    expect(handlers.refreshAuthentication).not.toHaveBeenCalled();
  });

  it("更新トークンがないと401をそのまま返す", async () => {
    const handlers = setup();
    handlers.getSession.mockRejectedValue(
      new RecorderApiError(401, "期限切れ"),
    );
    await expect(
      readSessionStatus({ ...handlers.options, refreshAuthentication: null }),
    ).rejects.toMatchObject({ status: 401 });
    expect(handlers.getSession).toHaveBeenCalledOnce();
  });

  it.each(["abort", "owner"])(
    "認証更新中の%s変更後はGETを行わない",
    async (change) => {
      const handlers = setup();
      const pending = deferred<void>();
      handlers.getSession.mockRejectedValueOnce(
        new RecorderApiError(401, "期限切れ"),
      );
      handlers.refreshAuthentication.mockReturnValue(pending.promise);
      let current = true;
      const result = readSessionStatus({
        ...handlers.options,
        isCurrent: () => current,
      });
      const rejected = expect(result).rejects.toThrow();
      await Promise.resolve();
      if (change === "abort") handlers.abort.abort();
      else current = false;
      pending.resolve();
      await rejected;
      expect(handlers.getSession).toHaveBeenCalledOnce();
    },
  );
});

describe("processingProgress", () => {
  it("内容やハッシュを保持せず安全な進捗だけを返す", () => {
    const result = processingProgress(
      session("completed", {
        processed_segment_count: 2,
        failed_segment_count: 1,
        record_id: recordId,
        audio_processing_incomplete: true,
        summary: "表示しない本文",
      }),
      "session-1",
    );
    expect(result).toEqual({
      status: "completed",
      totalSegments: 2,
      processedSegments: 2,
      failedSegments: 1,
      recordId,
      incomplete: true,
    });
  });

  it("旧版応答の省略されたカウンターを0として扱う", () => {
    expect(
      processingProgress(
        session("queued", {
          processed_segment_count: undefined,
          failed_segment_count: undefined,
        }),
        "session-1",
      ).processedSegments,
    ).toBe(0);
  });

  it.each([
    { id: "different-session" },
    { status: "unexpected" },
    { processed_segment_count: -1 },
    { processed_segment_count: 3 },
    { processed_segment_count: 0.5 },
    { failed_segment_count: 1 },
    { record_id: "https://outside.example/" },
    { record_id: "../new" },
  ])("不正な応答を表示へ渡さない: %j", (changes) => {
    expect(() =>
      processingProgress(session("queued", changes), "session-1"),
    ).toThrow("処理状況の応答を確認できませんでした。");
  });

  it("完了前は記録へのリンクを渡さない", () => {
    expect(
      processingProgress(
        session("processing", { record_id: recordId }),
        "session-1",
      ).recordId,
    ).toBeNull();
  });
});

describe("SessionStatusMonitor", () => {
  let monitor: SessionStatusMonitor;

  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    monitor?.stop();
    vi.useRealTimers();
  });

  function setup(
    load: (
      id: string,
      signal: AbortSignal,
    ) => Promise<ServerRecordingSession> = async () => session(),
  ) {
    const trackedLoad = vi.fn(load);
    const onProgress = vi.fn();
    const onIssue = vi.fn();
    const onLoading = vi.fn();
    monitor = new SessionStatusMonitor({
      load: trackedLoad,
      onProgress,
      onIssue,
      onLoading,
    });
    return { load: trackedLoad, onProgress, onIssue, onLoading };
  }

  it("5秒ごとに進捗を取得し完了後は自動・手動とも確認を止める", async () => {
    const handlers = setup(
      vi
        .fn()
        .mockResolvedValueOnce(session())
        .mockResolvedValueOnce(
          session("processing", { processed_segment_count: 1 }),
        )
        .mockResolvedValueOnce(
          session("completed", { processed_segment_count: 2 }),
        ),
    );
    monitor.start("session-1");
    await vi.advanceTimersByTimeAsync(0);
    expect(handlers.onProgress).toHaveBeenLastCalledWith(
      expect.objectContaining({ status: "queued" }),
    );
    await vi.advanceTimersByTimeAsync(5_000);
    expect(handlers.onProgress).toHaveBeenLastCalledWith(
      expect.objectContaining({ processedSegments: 1 }),
    );
    await vi.advanceTimersByTimeAsync(5_000);
    monitor.refresh();
    await vi.advanceTimersByTimeAsync(60_000);
    expect(handlers.load).toHaveBeenCalledTimes(3);
    expect(handlers.onLoading).toHaveBeenLastCalledWith(false);
  });

  it.each(["failed", "expired", "discarded"])(
    "%sでも自動確認を止める",
    async (status) => {
      const handlers = setup(vi.fn(async () => session(status)));
      monitor.start("session-1");
      await vi.advanceTimersByTimeAsync(60_000);
      expect(handlers.load).toHaveBeenCalledOnce();
    },
  );

  it("通信失敗時は間隔を延ばして再試行し最大60秒に制限する", async () => {
    const handlers = setup(vi.fn().mockRejectedValue(new Error("通信失敗")));
    monitor.start("session-1");
    await vi.advanceTimersByTimeAsync(0);
    expect(handlers.onIssue).toHaveBeenLastCalledWith("connection");
    for (const delay of [10_000, 20_000, 40_000, 60_000, 60_000]) {
      const count = handlers.load.mock.calls.length;
      await vi.advanceTimersByTimeAsync(delay - 1);
      expect(handlers.load).toHaveBeenCalledTimes(count);
      await vi.advanceTimersByTimeAsync(1);
      expect(handlers.load).toHaveBeenCalledTimes(count + 1);
    }
  });

  it("手動確認は待機時間を解除し回復後は5秒間隔に戻す", async () => {
    const handlers = setup(
      vi
        .fn()
        .mockRejectedValueOnce(new Error("通信失敗"))
        .mockResolvedValue(session("processing")),
    );
    monitor.start("session-1");
    await vi.advanceTimersByTimeAsync(0);
    monitor.refresh();
    await vi.advanceTimersByTimeAsync(0);
    expect(handlers.load).toHaveBeenCalledTimes(2);
    expect(handlers.onIssue).toHaveBeenLastCalledWith(null);
    await vi.advanceTimersByTimeAsync(5_000);
    expect(handlers.load).toHaveBeenCalledTimes(3);
  });

  it("取得中の手動確認でリクエストを重複させない", async () => {
    const pending = deferred<ServerRecordingSession>();
    const handlers = setup(vi.fn(() => pending.promise));
    monitor.start("session-1");
    monitor.refresh();
    await vi.advanceTimersByTimeAsync(10_000);
    expect(handlers.load).toHaveBeenCalledOnce();
    pending.resolve(session());
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(5_000);
    expect(handlers.load).toHaveBeenCalledTimes(2);
  });

  it("非表示・オフライン中は中断し復帰直後に状態だけを確認する", async () => {
    const pending = deferred<ServerRecordingSession>();
    const load = vi
      .fn<
        (id: string, signal: AbortSignal) => Promise<ServerRecordingSession>
      >()
      .mockImplementationOnce(() => pending.promise)
      .mockResolvedValue(session("completed"));
    const handlers = setup(load);
    monitor.start("session-1");
    monitor.setPaused(true);
    expect(load.mock.calls[0]![1].aborted).toBe(true);
    pending.resolve(session("processing"));
    await vi.advanceTimersByTimeAsync(60_000);
    expect(handlers.onProgress).not.toHaveBeenCalled();
    expect(load).toHaveBeenCalledOnce();
    monitor.setPaused(false);
    await vi.advanceTimersByTimeAsync(0);
    expect(load).toHaveBeenCalledTimes(2);
    expect(handlers.onProgress).toHaveBeenCalledOnce();
  });

  it("開始時点から停止中なら通信せず復帰を待つ", async () => {
    const handlers = setup();
    monitor.setPaused(true);
    monitor.start("session-1");
    await vi.advanceTimersByTimeAsync(60_000);
    expect(handlers.load).not.toHaveBeenCalled();
    monitor.setPaused(false);
    await vi.advanceTimersByTimeAsync(0);
    expect(handlers.load).toHaveBeenCalledOnce();
  });

  it("15秒timeout後は再試行し遅れて届いた応答を無視する", async () => {
    const pending = deferred<ServerRecordingSession>();
    const load = vi
      .fn<
        (id: string, signal: AbortSignal) => Promise<ServerRecordingSession>
      >()
      .mockImplementationOnce(() => pending.promise)
      .mockResolvedValue(session("completed"));
    const handlers = setup(load);
    monitor.start("session-1");
    await vi.advanceTimersByTimeAsync(15_000);
    expect(load.mock.calls[0]![1].aborted).toBe(true);
    expect(handlers.onIssue).toHaveBeenLastCalledWith("connection");
    pending.resolve(session("queued"));
    await vi.advanceTimersByTimeAsync(10_000);
    expect(handlers.onProgress).toHaveBeenCalledOnce();
    expect(handlers.onProgress).toHaveBeenLastCalledWith(
      expect.objectContaining({ status: "completed" }),
    );
  });

  it("別のセッションへ切り替えた後に古い応答を表示しない", async () => {
    const pending = deferred<ServerRecordingSession>();
    const handlers = setup(
      vi
        .fn()
        .mockImplementationOnce(() => pending.promise)
        .mockResolvedValue(session("completed", { id: "session-2" })),
    );
    monitor.start("session-1");
    monitor.start("session-2");
    pending.resolve(session("processing"));
    await vi.advanceTimersByTimeAsync(0);
    expect(handlers.onProgress).toHaveBeenCalledOnce();
    expect(handlers.onProgress).toHaveBeenLastCalledWith(
      expect.objectContaining({ status: "completed" }),
    );
  });

  it("離脱後はリクエストとタイマーを止め応答を表示しない", async () => {
    const pending = deferred<ServerRecordingSession>();
    const handlers = setup(vi.fn(() => pending.promise));
    monitor.start("session-1");
    monitor.stop();
    pending.resolve(session("completed"));
    await vi.advanceTimersByTimeAsync(60_000);
    expect(handlers.onProgress).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });

  it.each([
    [401, "authentication"],
    [403, "unavailable"],
    [404, "unavailable"],
  ] as const)("HTTP %sでは再試行しない", async (status, issue) => {
    const handlers = setup(
      vi.fn().mockRejectedValue(new RecorderApiError(status, "安全なエラー")),
    );
    monitor.start("session-1");
    await vi.advanceTimersByTimeAsync(60_000);
    expect(handlers.load).toHaveBeenCalledOnce();
    expect(handlers.onIssue).toHaveBeenLastCalledWith(issue);
  });

  it("別のセッションの応答を表示せず再確認する", async () => {
    const handlers = setup(
      vi.fn(async () => session("completed", { id: "different" })),
    );
    monitor.start("session-1");
    await vi.advanceTimersByTimeAsync(0);
    expect(handlers.onProgress).not.toHaveBeenCalled();
    expect(handlers.onIssue).toHaveBeenLastCalledWith("connection");
  });
});
