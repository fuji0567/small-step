import type { RecorderApi } from "./api";
import { MAX_LOCAL_SESSIONS, type SessionRepository } from "./storage";
import type { RecorderSegment } from "./types";
import type { UploadCoordinator } from "./upload";

interface Options {
  ownerId: string;
  mimeType: string;
  repository: SessionRepository;
  uploader: Pick<UploadCoordinator, "upload">;
  api: Pick<RecorderApi, "getSession">;
  beforeUpload: () => Promise<void>;
  isCurrent: () => boolean;
  isOnline: () => boolean;
  onPending: (count: number) => void;
  onAccepted: (id: string) => void;
  onBackpressure: () => void;
  onError: (error: unknown) => void;
}

// Local persistence finishes before the next minute starts; network work does not.
export class ContinuousUploadQueue {
  readonly #options: Options;
  #stopped = false;
  #draining: Promise<void> | null = null;
  #timer: ReturnType<typeof setTimeout> | null = null;
  #lastAccepted: string | null = null;

  constructor(options: Options) {
    this.#options = options;
  }

  async enqueue(segment: RecorderSegment): Promise<void> {
    const now = Date.now();
    await this.#options.repository.put({
      clientSessionId: crypto.randomUUID(),
      serverSessionId: null,
      ownerId: this.#options.ownerId,
      mimeType: this.#options.mimeType,
      createdAt: now,
      updatedAt: now,
      status: "uploading",
      durationMs: segment.durationMs,
      segments: [{ ...segment, sequence: 0 }],
    });
    const count = (await this.#options.repository.list()).length;
    if (this.#active()) {
      this.#options.onPending(count);
      if (count >= MAX_LOCAL_SESSIONS) this.#options.onBackpressure();
      void this.retry();
    }
  }

  retry(): Promise<void> {
    if (!this.#active()) return Promise.resolve();
    if (this.#draining) return this.#draining;
    if (this.#timer) clearTimeout(this.#timer);
    this.#timer = null;
    this.#draining = this.#drain().finally(() => {
      this.#draining = null;
      if (this.#active()) {
        this.#timer = setTimeout(() => void this.retry(), 10_000);
      }
    });
    return this.#draining;
  }

  stop(): void {
    this.#stopped = true;
    if (this.#timer) clearTimeout(this.#timer);
    this.#timer = null;
  }

  #active(): boolean {
    return !this.#stopped && this.#options.isCurrent();
  }

  async #drain(): Promise<void> {
    try {
      if (!this.#options.isOnline()) return;
      if (this.#lastAccepted) {
        const previous = await this.#options.api.getSession(this.#lastAccepted);
        if (!this.#active()) return;
        if (
          !["completed", "failed", "expired", "discarded"].includes(
            previous.status,
          )
        )
          return;
        this.#lastAccepted = null;
      }
      const sessions = await this.#options.repository.list();
      if (!this.#active()) return;
      this.#options.onPending(sessions.length);
      const session = sessions
        .filter(
          (item) =>
            item.ownerId === this.#options.ownerId &&
            item.status === "uploading" &&
            item.segments.length > 0,
        )
        .sort((a, b) => a.createdAt - b.createdAt)[0];
      if (!session) return;
      await this.#options.beforeUpload();
      if (!this.#active()) return;
      const id = await this.#options.uploader.upload(session);
      if (!this.#active()) return;
      this.#lastAccepted = id;
      const remaining = (await this.#options.repository.list()).length;
      if (!this.#active()) return;
      this.#options.onPending(remaining);
      this.#options.onAccepted(id);
    } catch (error) {
      if (this.#active()) this.#options.onError(error);
    }
  }
}
