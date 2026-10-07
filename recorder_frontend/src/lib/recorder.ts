import type { RecorderSegment } from "./types";

export const SEGMENT_DURATION_MS = 60_000;
export const MAX_RECORDING_DURATION_MS = 60 * 60_000;
export const MAX_CONTINUOUS_RECORDING_DURATION_MS =
  12 * MAX_RECORDING_DURATION_MS;

export type RecordingPhase = "idle" | "recording" | "paused" | "stopped";

export interface RecorderLike {
  state: RecordingState;
  ondataavailable: ((event: BlobEvent) => void) | null;
  onstop: ((event: Event) => void) | null;
  onerror: ((event: ErrorEvent) => void) | null;
  start(): void;
  stop(): void;
}

export interface RecorderControllerOptions {
  stream: MediaStream;
  mimeType: string;
  maxDurationMs?: number;
  createRecorder: (
    stream: MediaStream,
    options: MediaRecorderOptions,
  ) => RecorderLike;
  now?: () => number;
  setTimer?: (
    callback: () => void,
    delay: number,
  ) => ReturnType<typeof setTimeout>;
  clearTimer?: (timer: ReturnType<typeof setTimeout>) => void;
  onSegment: (segment: RecorderSegment) => void | Promise<void>;
  onChange?: () => void;
  onInterruption?: (message: string) => void;
}

export function selectSupportedMimeType(
  isTypeSupported: (mimeType: string) => boolean,
): string | null {
  const candidates = ["audio/mp4", "audio/webm;codecs=opus", "audio/webm"];
  return candidates.find(isTypeSupported) ?? null;
}

export class RecorderController {
  phase: RecordingPhase = "idle";
  totalDurationMs = 0;
  segmentCount = 0;
  readonly mimeType: string;
  readonly #maxDurationMs: number;
  readonly #options: RecorderControllerOptions;
  readonly #now: () => number;
  readonly #setTimer: NonNullable<RecorderControllerOptions["setTimer"]>;
  readonly #clearTimer: NonNullable<RecorderControllerOptions["clearTimer"]>;
  #recorder: RecorderLike | null = null;
  #timer: ReturnType<typeof setTimeout> | null = null;
  #segmentStartedAt = 0;
  #nextPhase: RecordingPhase = "recording";
  #pendingDurationMs = 0;
  #chunks: Blob[] = [];
  #finishing = false;
  #stream: MediaStream;
  #settled: Promise<void> = Promise.resolve();
  #resolveSettled: (() => void) | null = null;

  constructor(options: RecorderControllerOptions) {
    this.#options = options;
    this.#stream = options.stream;
    this.mimeType = options.mimeType;
    this.#maxDurationMs = options.maxDurationMs ?? MAX_RECORDING_DURATION_MS;
    if (
      !Number.isFinite(this.#maxDurationMs) ||
      this.#maxDurationMs <= 0 ||
      this.#maxDurationMs > MAX_CONTINUOUS_RECORDING_DURATION_MS
    ) {
      throw new Error("録音時間の上限が不正です。");
    }
    this.#now = options.now ?? Date.now;
    this.#setTimer =
      options.setTimer ??
      ((callback, delay) => globalThis.setTimeout(callback, delay));
    this.#clearTimer =
      options.clearTimer ?? ((timer) => globalThis.clearTimeout(timer));
  }

  get elapsedMs(): number {
    return (
      this.totalDurationMs +
      (this.phase === "recording" && !this.#finishing
        ? Math.max(0, this.#now() - this.#segmentStartedAt)
        : 0)
    );
  }

  get isFinalizing(): boolean {
    return this.#finishing;
  }

  whenSettled(): Promise<void> {
    return this.#settled;
  }

  start(): void {
    if (this.phase !== "idle")
      throw new Error("録音はすでに開始されています。");
    this.phase = "recording";
    this.#beginSegment();
  }

  pause(): void {
    if (this.phase !== "recording") return;
    this.#finishSegment("paused");
  }

  resume(): void {
    if (this.phase !== "paused") return;
    if (this.#finishing) {
      this.#nextPhase = "recording";
      this.phase = "recording";
      this.#changed();
      return;
    }
    this.phase = "recording";
    this.#beginSegment();
  }

  replaceStream(stream: MediaStream): void {
    if (this.phase !== "paused") {
      throw new Error("マイクは一時停止中にだけ切り替えられます。");
    }
    this.#stream = stream;
  }

  stop(): void {
    if (this.phase === "recording") this.#finishSegment("stopped");
    else if (this.phase === "paused") {
      if (this.#finishing) {
        this.#nextPhase = "stopped";
      } else {
        for (const track of this.#stream.getTracks()) track.stop();
      }
      this.phase = "stopped";
      this.#changed();
    }
  }

  microphoneInterrupted(): void {
    this.interrupt(
      "マイクが中断されたため録音を一時停止しました。マイクを確認して再開してください。",
    );
  }

  interrupt(message: string): void {
    if (this.phase !== "recording") return;
    this.#options.onInterruption?.(message);
    this.#finishSegment("paused");
  }

  #beginSegment(): void {
    this.#chunks = [];
    this.#finishing = false;
    this.#segmentStartedAt = this.#now();
    this.#settled = new Promise<void>((resolve) => {
      this.#resolveSettled = resolve;
    });
    const recorder = this.#options.createRecorder(
      this.#stream,
      this.mimeType ? { mimeType: this.mimeType } : {},
    );
    this.#recorder = recorder;
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) this.#chunks.push(event.data);
    };
    recorder.onerror = () => this.microphoneInterrupted();
    recorder.onstop = () => {
      // The browser can stop capture without an application stop request.
      if (!this.#finishing) this.microphoneInterrupted();
      else void this.#completeSegment();
    };
    recorder.start();

    const remaining = this.#maxDurationMs - this.totalDurationMs;
    const delay = Math.min(SEGMENT_DURATION_MS, remaining);
    this.#timer = this.#setTimer(() => {
      const reachesLimit = this.#now() - this.#segmentStartedAt >= remaining;
      this.#finishSegment(reachesLimit ? "stopped" : "recording");
    }, delay);
    this.#changed();
  }

  #finishSegment(nextPhase: RecordingPhase): void {
    if (this.#finishing) {
      if (nextPhase === "stopped" || this.#nextPhase === "recording") {
        this.#nextPhase = nextPhase;
        this.phase = nextPhase;
        this.#changed();
      }
      return;
    }
    if (!this.#recorder) return;
    this.#finishing = true;
    this.#nextPhase = nextPhase;
    if (this.#timer !== null) this.#clearTimer(this.#timer);
    this.#timer = null;
    const duration = Math.min(
      Math.max(0, this.#now() - this.#segmentStartedAt),
      this.#maxDurationMs - this.totalDurationMs,
    );
    this.#pendingDurationMs = duration;
    this.totalDurationMs += duration;
    this.phase = nextPhase;
    if (this.#recorder.state !== "inactive") this.#recorder.stop();
    else void this.#completeSegment();
    this.#changed();
  }

  async #completeSegment(): Promise<void> {
    const recorder = this.#recorder;
    if (!recorder) return;
    this.#recorder = null;
    const durationMs = this.#pendingDurationMs;
    let persistenceFailed = false;
    try {
      if (durationMs > 0 && this.#chunks.length > 0) {
        const segment: RecorderSegment = {
          sequence: this.segmentCount,
          blob: new Blob(this.#chunks, {
            type: this.mimeType || this.#chunks[0]?.type,
          }),
          durationMs,
        };
        await this.#options.onSegment(segment);
        this.segmentCount += 1;
      }
    } catch {
      persistenceFailed = true;
      this.totalDurationMs = Math.max(0, this.totalDurationMs - durationMs);
      this.#nextPhase = "paused";
      this.phase = "paused";
      this.#options.onInterruption?.(
        "録音データを端末に保存できませんでした。空き容量を確認してから再開してください。",
      );
    } finally {
      this.#chunks = [];
      this.#pendingDurationMs = 0;
      this.#finishing = false;
      const resolveSettled = this.#resolveSettled;
      this.#resolveSettled = null;
      resolveSettled?.();
    }
    if (
      !persistenceFailed &&
      this.#nextPhase === "recording" &&
      this.totalDurationMs < this.#maxDurationMs
    ) {
      this.phase = "recording";
      this.#beginSegment();
      return;
    }
    if (this.#nextPhase === "stopped") {
      for (const track of this.#stream.getTracks()) track.stop();
    }
    this.#changed();
  }

  #changed(): void {
    this.#options.onChange?.();
  }
}
