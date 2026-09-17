import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ContinuousUploadQueue } from "./continuous-upload";
import type { SessionRepository } from "./storage";
import type {
  LocalRecordingSession,
  RecorderSegment,
  ServerRecordingSession,
} from "./types";

const segment: RecorderSegment = {
  sequence: 12,
  durationMs: 60_000,
  blob: new Blob(["audio"], { type: "audio/mp4" }),
};

function setup() {
  const saved = new Map<string, LocalRecordingSession>();
  const repository: SessionRepository = {
    list: async () => [...saved.values()],
    put: async (session) => {
      saved.set(session.clientSessionId, session);
    },
    delete: async (id) => {
      saved.delete(id);
    },
    cleanup: async () => [],
  };
  const upload = vi.fn(async (session: LocalRecordingSession) => {
    await repository.delete(session.clientSessionId);
    return `server-${session.clientSessionId}`;
  });
  const getSession = vi.fn(
    async () => ({ status: "processing" }) as ServerRecordingSession,
  );
  const isCurrent = vi.fn(() => true);
  const isOnline = vi.fn(() => true);
  const beforeUpload = vi.fn(async () => undefined);
  const onAccepted = vi.fn();
  const onPending = vi.fn();
  const onBackpressure = vi.fn();
  const onError = vi.fn();
  const queue = new ContinuousUploadQueue({
    ownerId: "owner",
    mimeType: "audio/mp4",
    repository,
    uploader: { upload },
    api: { getSession },
    isCurrent,
    isOnline,
    beforeUpload,
    onAccepted,
    onPending,
    onBackpressure,
    onError,
  });
  return {
    queue,
    saved,
    upload,
    getSession,
    isCurrent,
    isOnline,
    beforeUpload,
    onAccepted,
    onPending,
    onBackpressure,
    onError,
  };
}

describe("ContinuousUploadQueue", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("各区間を別ID・連番0で保存し通信完了を待たずに戻る", async () => {
    const s = setup();
    let finish!: (id: string) => void;
    s.upload.mockImplementationOnce(
      () =>
        new Promise<string>((resolve) => {
          finish = resolve;
        }),
    );
    await s.queue.enqueue(segment);
    await Promise.resolve();
    await s.queue.enqueue(segment);
    expect(s.saved.size).toBe(2);
    expect(
      [...s.saved.values()].every((item) => item.segments[0]?.sequence === 0),
    ).toBe(true);
    expect(s.upload).toHaveBeenCalledOnce();
    finish("server");
    await s.queue.retry();
    s.queue.stop();
  });

  it("受付後に端末音声を削除し処理完了まで次の区間を送らない", async () => {
    const s = setup();
    await s.queue.enqueue(segment);
    await s.queue.retry();
    expect(s.saved.size).toBe(0);
    expect(s.onAccepted).toHaveBeenCalledOnce();
    await s.queue.enqueue(segment);
    await s.queue.retry();
    expect(s.upload).toHaveBeenCalledOnce();
    s.getSession.mockResolvedValue({
      status: "completed",
    } as ServerRecordingSession);
    await s.queue.retry();
    expect(s.upload).toHaveBeenCalledTimes(2);
    s.queue.stop();
  });

  it("通信断で最大3区間を保持し一時停止を要求するが自動再開しない", async () => {
    const s = setup();
    s.isOnline.mockReturnValue(false);
    for (let i = 0; i < 3; i++) await s.queue.enqueue(segment);
    expect(s.saved.size).toBe(3);
    expect(s.onBackpressure).toHaveBeenCalledOnce();
    expect(s.upload).not.toHaveBeenCalled();
    s.isOnline.mockReturnValue(true);
    await s.queue.retry();
    expect(s.saved.size).toBe(2);
    s.queue.stop();
  });

  it("送信失敗後も同じIDのデータを保持して再試行する", async () => {
    const s = setup();
    s.upload.mockRejectedValueOnce(new Error("network"));
    await s.queue.enqueue(segment);
    await s.queue.retry();
    const id = [...s.saved.keys()][0];
    expect(s.onError).toHaveBeenCalledOnce();
    await vi.advanceTimersByTimeAsync(10_000);
    expect(s.upload.mock.calls[1]?.[0].clientSessionId).toBe(id);
    expect(s.saved.size).toBe(0);
    s.queue.stop();
  });

  it("別の所有者と手動送信待ちの録音を自動送信しない", async () => {
    const s = setup();
    s.isOnline.mockReturnValue(false);
    await s.queue.enqueue(segment);
    const sample = [...s.saved.values()][0]!;
    s.saved.clear();
    s.saved.set("foreign", {
      ...sample,
      clientSessionId: "foreign",
      ownerId: "other",
    });
    s.saved.set("manual", {
      ...sample,
      clientSessionId: "manual",
      status: "pending",
    });
    s.isOnline.mockReturnValue(true);
    await s.queue.retry();
    expect(s.upload).not.toHaveBeenCalled();
    s.queue.stop();
  });

  it("停止後の末尾は保存するが送信やタイマーを継続しない", async () => {
    const s = setup();
    s.queue.stop();
    await s.queue.enqueue({ ...segment, durationMs: 5_000 });
    await vi.advanceTimersByTimeAsync(30_000);
    expect([...s.saved.values()][0]?.durationMs).toBe(5_000);
    expect(s.upload).not.toHaveBeenCalled();
    expect(s.onPending).not.toHaveBeenCalled();
  });

  it("認証更新中に所有者が変わった場合は送信しない", async () => {
    const s = setup();
    s.beforeUpload.mockImplementation(async () => {
      s.isCurrent.mockReturnValue(false);
    });
    await s.queue.enqueue(segment);
    await s.queue.retry();
    expect(s.upload).not.toHaveBeenCalled();
    s.queue.stop();
  });
});
