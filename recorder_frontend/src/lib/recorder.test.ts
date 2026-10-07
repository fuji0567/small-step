import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  MAX_RECORDING_DURATION_MS,
  MAX_CONTINUOUS_RECORDING_DURATION_MS,
  RecorderController,
  SEGMENT_DURATION_MS,
  selectSupportedMimeType,
  type RecorderLike,
} from "./recorder";
import type { RecorderSegment } from "./types";

class FakeRecorder implements RecorderLike {
  state: RecordingState = "inactive";
  ondataavailable: ((event: BlobEvent) => void) | null = null;
  onstop: ((event: Event) => void) | null = null;
  onerror: ((event: ErrorEvent) => void) | null = null;

  start(): void {
    this.state = "recording";
  }

  stop(): void {
    this.state = "inactive";
    this.ondataavailable?.({
      data: new Blob(["audio"], { type: "audio/mp4" }),
    } as BlobEvent);
    this.onstop?.(new Event("stop"));
  }
}

describe("selectSupportedMimeType", () => {
  it("MP4/AACを最優先する", () => {
    expect(selectSupportedMimeType(() => true)).toBe("audio/mp4");
  });

  it("MP4がない場合はWebM/Opusへフォールバックする", () => {
    expect(selectSupportedMimeType((type) => type.includes("webm"))).toBe(
      "audio/webm;codecs=opus",
    );
  });

  it("対応形式がなければnullを返す", () => {
    expect(selectSupportedMimeType(() => false)).toBeNull();
  });
});

describe("RecorderController", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  function setup(maxDurationMs?: number) {
    const recorders: FakeRecorder[] = [];
    const segments: RecorderSegment[] = [];
    const interruptions: string[] = [];
    const controller = new RecorderController({
      stream: { getTracks: () => [] } as unknown as MediaStream,
      mimeType: "audio/mp4",
      maxDurationMs,
      createRecorder: () => {
        const recorder = new FakeRecorder();
        recorders.push(recorder);
        return recorder;
      },
      now: Date.now,
      onSegment: (segment) => {
        segments.push(segment);
      },
      onInterruption: (message) => interruptions.push(message),
    });
    return { controller, recorders, segments, interruptions };
  }

  it("1分ごとにstopして独立した次のRecorderを開始する", async () => {
    const { controller, recorders, segments } = setup();
    controller.start();
    await vi.advanceTimersByTimeAsync(SEGMENT_DURATION_MS);

    expect(recorders).toHaveLength(2);
    expect(segments).toHaveLength(1);
    expect(segments[0]).toMatchObject({ sequence: 0, durationMs: 60_000 });
    expect(controller.phase).toBe("recording");
  });

  it("ブラウザ組み込みタイマーを正しいreceiverで呼び出す", () => {
    const strictSetTimeout = vi.fn(function (this: unknown) {
      if (this !== globalThis) throw new TypeError("Illegal invocation");
      return 1 as unknown as ReturnType<typeof setTimeout>;
    });
    const strictClearTimeout = vi.fn(function (this: unknown) {
      if (this !== globalThis) throw new TypeError("Illegal invocation");
    });
    vi.stubGlobal("setTimeout", strictSetTimeout);
    vi.stubGlobal("clearTimeout", strictClearTimeout);

    const controller = new RecorderController({
      stream: { getTracks: () => [] } as unknown as MediaStream,
      mimeType: "audio/mp4",
      createRecorder: () => new FakeRecorder(),
      now: Date.now,
      onSegment: vi.fn(),
    });

    expect(() => controller.start()).not.toThrow();
    expect(() => controller.pause()).not.toThrow();
    expect(strictSetTimeout).toHaveBeenCalledOnce();
    expect(strictClearTimeout).toHaveBeenCalledOnce();
  });

  it("一時停止時間を実録音時間に含めない", async () => {
    const { controller } = setup();
    controller.start();
    await vi.advanceTimersByTimeAsync(10_000);
    controller.pause();
    expect(controller.totalDurationMs).toBe(10_000);

    await vi.advanceTimersByTimeAsync(30_000);
    expect(controller.elapsedMs).toBe(10_000);
    controller.resume();
    await vi.advanceTimersByTimeAsync(5_000);
    controller.stop();
    expect(controller.totalDurationMs).toBe(15_000);
  });

  it("実録音60分で自動停止する", async () => {
    const { controller, segments } = setup();
    controller.start();
    await vi.advanceTimersByTimeAsync(MAX_RECORDING_DURATION_MS);

    expect(controller.phase).toBe("stopped");
    expect(controller.totalDurationMs).toBe(MAX_RECORDING_DURATION_MS);
    expect(segments).toHaveLength(60);
  });

  it("背面でタイマーが遅れても上限を過ぎたら停止しマイクを解放する", async () => {
    const stopTrack = vi.fn();
    const segments: RecorderSegment[] = [];
    const now = vi.fn(() => 0);
    const controller = new RecorderController({
      stream: {
        getTracks: () => [{ stop: stopTrack }],
      } as unknown as MediaStream,
      mimeType: "audio/mp4",
      createRecorder: () => new FakeRecorder(),
      now,
      onSegment: (segment) => {
        segments.push(segment);
      },
    });
    controller.start();
    now.mockReturnValue(MAX_RECORDING_DURATION_MS + 10_000);
    await vi.advanceTimersByTimeAsync(SEGMENT_DURATION_MS);

    expect(controller.phase).toBe("stopped");
    expect(segments[0]?.durationMs).toBe(MAX_RECORDING_DURATION_MS);
    expect(stopTrack).toHaveBeenCalledOnce();
  });

  it("連続モードは60分を超えて録音し12時間で停止する", async () => {
    const { controller, segments } = setup(
      MAX_CONTINUOUS_RECORDING_DURATION_MS,
    );
    controller.start();
    await vi.advanceTimersByTimeAsync(MAX_RECORDING_DURATION_MS);
    expect(controller.phase).toBe("recording");
    await vi.advanceTimersByTimeAsync(
      MAX_CONTINUOUS_RECORDING_DURATION_MS - MAX_RECORDING_DURATION_MS,
    );
    expect(controller.phase).toBe("stopped");
    expect(segments).toHaveLength(720);
  });

  it("マイク中断で端数を確定して明示再開待ちにする", async () => {
    const { controller, segments, interruptions } = setup();
    controller.start();
    await vi.advanceTimersByTimeAsync(8_000);
    controller.microphoneInterrupted();

    expect(controller.phase).toBe("paused");
    expect(segments[0]?.durationMs).toBe(8_000);
    expect(interruptions[0]).toContain("マイクが中断");
  });

  it("ブラウザによる予期しない停止でも端数を保存し自動再開しない", async () => {
    const { controller, recorders, segments, interruptions } = setup();
    controller.start();
    await vi.advanceTimersByTimeAsync(8_000);
    recorders[0].stop();
    await controller.whenSettled();

    expect(controller.phase).toBe("paused");
    expect(segments[0]?.durationMs).toBe(8_000);
    expect(interruptions[0]).toContain("マイクが中断");
    expect(recorders).toHaveLength(1);
  });

  it("1分境界の保存中に停止しても次のRecorderを開始しない", async () => {
    let release!: () => void;
    const persistence = new Promise<void>((resolve) => {
      release = resolve;
    });
    const recorders: FakeRecorder[] = [];
    const controller = new RecorderController({
      stream: { getTracks: () => [] } as unknown as MediaStream,
      mimeType: "audio/mp4",
      createRecorder: () => {
        const recorder = new FakeRecorder();
        recorders.push(recorder);
        return recorder;
      },
      now: Date.now,
      onSegment: () => persistence,
    });
    controller.start();
    await vi.advanceTimersByTimeAsync(SEGMENT_DURATION_MS);
    controller.stop();
    release();
    await persistence;
    await Promise.resolve();

    expect(controller.phase).toBe("stopped");
    expect(recorders).toHaveLength(1);
  });

  it("一時停止の確定中に停止してもマイクを解放する", async () => {
    let release!: () => void;
    const persistence = new Promise<void>((resolve) => {
      release = resolve;
    });
    const stopTrack = vi.fn();
    const controller = new RecorderController({
      stream: {
        getTracks: () => [{ stop: stopTrack }],
      } as unknown as MediaStream,
      mimeType: "audio/mp4",
      createRecorder: () => new FakeRecorder(),
      now: Date.now,
      onSegment: () => persistence,
    });
    controller.start();
    await vi.advanceTimersByTimeAsync(1_000);
    controller.pause();
    controller.stop();
    release();
    await persistence;
    await Promise.resolve();

    expect(controller.phase).toBe("stopped");
    expect(stopTrack).toHaveBeenCalledOnce();
  });

  it("非同期stopの末尾保存が終わるまでwhenSettledが待つ", async () => {
    let stopped!: () => void;
    class AsyncRecorder extends FakeRecorder {
      override stop(): void {
        this.state = "inactive";
        stopped = () => {
          this.ondataavailable?.({
            data: new Blob(["tail"], { type: "audio/mp4" }),
          } as BlobEvent);
          this.onstop?.(new Event("stop"));
        };
      }
    }
    const persisted: RecorderSegment[] = [];
    const controller = new RecorderController({
      stream: { getTracks: () => [] } as unknown as MediaStream,
      mimeType: "audio/mp4",
      createRecorder: () => new AsyncRecorder(),
      now: Date.now,
      onSegment: async (segment) => {
        await Promise.resolve();
        persisted.push(segment);
      },
    });
    controller.start();
    await vi.advanceTimersByTimeAsync(1_000);
    controller.stop();
    let settled = false;
    void controller.whenSettled().then(() => (settled = true));
    await Promise.resolve();
    expect(settled).toBe(false);

    stopped();
    await controller.whenSettled();
    expect(persisted).toHaveLength(1);
    expect(persisted[0]?.sequence).toBe(0);
  });

  it("端末保存に失敗したセグメントは採番せず一時停止する", async () => {
    const interruptions: string[] = [];
    const controller = new RecorderController({
      stream: { getTracks: () => [] } as unknown as MediaStream,
      mimeType: "audio/mp4",
      createRecorder: () => new FakeRecorder(),
      now: Date.now,
      onSegment: async () => {
        throw new Error("quota");
      },
      onInterruption: (message) => interruptions.push(message),
    });
    controller.start();
    await vi.advanceTimersByTimeAsync(1_000);
    controller.pause();
    await controller.whenSettled();

    expect(controller.phase).toBe("paused");
    expect(controller.segmentCount).toBe(0);
    expect(interruptions[0]).toContain("保存できませんでした");
  });
});
