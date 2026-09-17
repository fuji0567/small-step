import { RecorderApiError, type RecorderApi } from "./api";
import { AuthRefreshError } from "./auth";
import type { ServerRecordingSession } from "./types";

export type ProcessingStatus =
  "queued" | "processing" | "completed" | "failed" | "expired" | "discarded";

export interface ProcessingProgress {
  status: ProcessingStatus;
  totalSegments: number;
  processedSegments: number;
  failedSegments: number;
  recordId: string | null;
  incomplete: boolean;
}

export type StatusIssue = "connection" | "unavailable" | "authentication";

interface ReadStatusOptions {
  api: RecorderApi;
  id: string;
  signal: AbortSignal;
  isCurrent: () => boolean;
  refreshAuthentication: (() => Promise<void>) | null;
}

export async function readSessionStatus({
  api,
  id,
  signal,
  isCurrent,
  refreshAuthentication,
}: ReadStatusOptions): Promise<ServerRecordingSession> {
  const checkCurrent = () => {
    signal.throwIfAborted();
    if (!isCurrent()) throw new Error("状態確認を停止しました。");
  };
  checkCurrent();
  try {
    return await api.getSession(id, signal);
  } catch (error) {
    if (
      !(error instanceof RecorderApiError) ||
      error.status !== 401 ||
      !refreshAuthentication
    )
      throw error;
    checkCurrent();
    try {
      await refreshAuthentication();
    } catch (refreshError) {
      if (
        refreshError instanceof AuthRefreshError &&
        [400, 401].includes(refreshError.status)
      )
        throw new RecorderApiError(401, "ログインを更新できませんでした。");
      throw refreshError;
    }
    checkCurrent();
    return api.getSession(id, signal);
  }
}

const statuses: ProcessingStatus[] = [
  "queued",
  "processing",
  "completed",
  "failed",
  "expired",
  "discarded",
];
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// 表示用には内容・ハッシュ・音声を持たない進捗だけを取り出す。
export function processingProgress(
  session: ServerRecordingSession,
  expectedId: string,
): ProcessingProgress {
  if (
    !session ||
    session.id !== expectedId ||
    !statuses.includes(session.status as ProcessingStatus) ||
    !Array.isArray(session.segments)
  ) {
    throw new Error("処理状況の応答を確認できませんでした。");
  }
  const total = session.segments.length;
  const processed = session.processed_segment_count ?? 0;
  const failed = session.failed_segment_count ?? 0;
  if (
    !Number.isSafeInteger(processed) ||
    processed < 0 ||
    processed > total ||
    !Number.isSafeInteger(failed) ||
    failed < 0 ||
    failed > processed ||
    (session.record_id != null &&
      (typeof session.record_id !== "string" ||
        !uuid.test(session.record_id))) ||
    (session.audio_processing_incomplete != null &&
      typeof session.audio_processing_incomplete !== "boolean")
  ) {
    throw new Error("処理状況の応答を確認できませんでした。");
  }
  return {
    status: session.status as ProcessingStatus,
    totalSegments: total,
    processedSegments: processed,
    failedSegments: failed,
    recordId:
      session.status === "completed" ? (session.record_id ?? null) : null,
    incomplete: session.audio_processing_incomplete === true,
  };
}

interface MonitorOptions {
  load: (id: string, signal: AbortSignal) => Promise<ServerRecordingSession>;
  onProgress: (progress: ProcessingProgress) => void;
  onIssue: (issue: StatusIssue | null) => void;
  onLoading: (loading: boolean) => void;
}

interface ActiveRequest {
  cancel: () => void;
}

export class SessionStatusMonitor {
  readonly #options: MonitorOptions;
  #id: string | null = null;
  #paused = false;
  #terminal = false;
  #version = 0;
  #failures = 0;
  #timer: ReturnType<typeof setTimeout> | null = null;
  #request: ActiveRequest | null = null;

  constructor(options: MonitorOptions) {
    this.#options = options;
  }

  start(id: string): void {
    this.stop();
    this.#id = id;
    this.#terminal = false;
    this.#failures = 0;
    this.#options.onIssue(null);
    this.refresh();
  }

  stop(): void {
    this.#id = null;
    this.#cancel();
  }

  setPaused(paused: boolean): void {
    if (paused === this.#paused) return;
    this.#paused = paused;
    if (paused) this.#cancel();
    else this.refresh();
  }

  refresh(): void {
    if (!this.#id || this.#paused || this.#terminal || this.#request) return;
    if (this.#timer) clearTimeout(this.#timer);
    this.#timer = null;
    this.#failures = 0;
    void this.#poll();
  }

  #cancel(): void {
    this.#version++;
    if (this.#timer) clearTimeout(this.#timer);
    this.#timer = null;
    const request = this.#request;
    this.#request = null;
    request?.cancel();
    this.#options.onLoading(false);
  }

  async #poll(): Promise<void> {
    const id = this.#id;
    if (!id || this.#paused || this.#terminal || this.#request) return;
    const version = this.#version;
    const abort = new AbortController();
    let cancel = () => undefined as void;
    const cancelled = new Promise<never>((_, reject) => {
      cancel = () => {
        reject(new Error("状態確認を停止しました。"));
        abort.abort();
      };
    });
    const request: ActiveRequest = { cancel };
    this.#request = request;
    const timeout = setTimeout(cancel, 15_000);
    this.#options.onLoading(true);
    try {
      // fetchが中断を無視しても、離脱・timeout後の応答を画面へ反映しない。
      const session = await Promise.race([
        this.#options.load(id, abort.signal),
        cancelled,
      ]);
      if (version !== this.#version) return;
      const progress = processingProgress(session, id);
      this.#terminal = !["queued", "processing"].includes(progress.status);
      this.#failures = 0;
      this.#options.onIssue(null);
      this.#options.onProgress(progress);
    } catch (error) {
      if (version !== this.#version) return;
      this.#failures++;
      if (error instanceof RecorderApiError && error.status === 401) {
        this.#terminal = true;
        this.#options.onIssue("authentication");
      } else if (
        error instanceof RecorderApiError &&
        [403, 404].includes(error.status)
      ) {
        this.#terminal = true;
        this.#options.onIssue("unavailable");
      } else {
        this.#options.onIssue("connection");
      }
    } finally {
      clearTimeout(timeout);
      if (this.#request === request) this.#request = null;
      if (version === this.#version) {
        this.#options.onLoading(false);
        if (this.#id && !this.#paused && !this.#terminal) {
          const delay = Math.min(
            60_000,
            5_000 * 2 ** Math.min(this.#failures, 4),
          );
          this.#timer = setTimeout(() => {
            this.#timer = null;
            void this.#poll();
          }, delay);
        }
      }
    }
  }
}
