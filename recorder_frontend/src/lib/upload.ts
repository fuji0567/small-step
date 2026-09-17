import type { RecorderApi } from "./api";
import type { SessionRepository } from "./storage";
import type { LocalRecordingSession, RecorderSegment } from "./types";

export async function sha256(blob: Blob): Promise<string> {
  const digest = await crypto.subtle.digest(
    "SHA-256",
    await blob.arrayBuffer(),
  );
  return [...new Uint8Array(digest)]
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
}

function extensionFor(mimeType: string): string {
  return mimeType.startsWith("audio/mp4") ? "m4a" : "webm";
}

export interface UploadCoordinatorOptions {
  api: RecorderApi;
  repository: SessionRepository;
}

export class UploadCoordinator {
  readonly #api: RecorderApi;
  readonly #repository: SessionRepository;
  readonly #uploads = new Map<string, Promise<string>>();

  constructor(options: UploadCoordinatorOptions) {
    this.#api = options.api;
    this.#repository = options.repository;
  }

  upload(session: LocalRecordingSession): Promise<string> {
    const existing = this.#uploads.get(session.clientSessionId);
    if (existing) return existing;
    const pending = this.#upload(session).finally(() =>
      this.#uploads.delete(session.clientSessionId),
    );
    this.#uploads.set(session.clientSessionId, pending);
    return pending;
  }

  async #upload(session: LocalRecordingSession): Promise<string> {
    let serverId = session.serverSessionId;
    if (!serverId) {
      const created = await this.#api.createSession(session.clientSessionId);
      serverId = created.id;
      session = {
        ...session,
        serverSessionId: serverId,
        status: "uploading",
        updatedAt: Date.now(),
      };
      await this.#repository.put(session);
    }

    const server = await this.#api.getSession(serverId);
    if (
      ["queued", "processing", "completed", "failed"].includes(server.status)
    ) {
      await this.#repository.delete(session.clientSessionId);
      return serverId;
    }
    if (server.status !== "draft") {
      throw new Error("この録音セッションは再送できない状態です。");
    }
    const received = new Map(
      server.segments.map((segment) => [segment.sequence, segment]),
    );
    for (const segment of [...session.segments].sort(
      (a, b) => a.sequence - b.sequence,
    )) {
      const hash = segment.sha256 ?? (await sha256(segment.blob));
      const existing = received.get(segment.sequence);
      if (
        existing?.sha256 === hash &&
        existing.duration_ms === segment.durationMs &&
        existing.size_bytes === segment.blob.size
      ) {
        continue;
      }
      if (existing) throw new Error("送信済みデータと内容が一致しません。");
      await this.#api.uploadSegment(
        serverId,
        segment.sequence,
        this.#formData(segment, hash),
      );
    }
    await this.#api.finalize(serverId);
    await this.#repository.delete(session.clientSessionId);
    return serverId;
  }

  async retryOwned(
    ownerId: string,
    excludedClientSessionId?: string,
  ): Promise<{ attempted: number; foreignExists: boolean }> {
    await this.#repository.cleanup();
    const sessions = await this.#repository.list();
    const owned = sessions.filter(
      (session) =>
        session.ownerId === ownerId &&
        session.clientSessionId !== excludedClientSessionId &&
        session.status === "uploading" &&
        session.segments.length > 0,
    );
    for (const session of owned) {
      try {
        await this.upload(session);
      } catch {
        // 起動時の再送は利用者の操作を妨げない。明示的な再送でエラーを表示する。
      }
    }
    return {
      attempted: owned.length,
      foreignExists: sessions.some((session) => session.ownerId !== ownerId),
    };
  }

  #formData(segment: RecorderSegment, hash: string): FormData {
    const form = new FormData();
    form.append(
      "file",
      segment.blob,
      `segment-${segment.sequence}.${extensionFor(segment.blob.type)}`,
    );
    form.append("duration_ms", String(segment.durationMs));
    form.append("sha256", hash);
    return form;
  }
}
