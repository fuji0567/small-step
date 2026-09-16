import { IDBFactory } from "fake-indexeddb";
import { describe, expect, it } from "vitest";

import { IndexedDbSessionRepository, SESSION_TTL_MS } from "./storage";
import type { LocalRecordingSession } from "./types";

function session(id: string, updatedAt: number): LocalRecordingSession {
  return {
    clientSessionId: id,
    serverSessionId: null,
    ownerId: "teacher-1",
    createdAt: updatedAt,
    updatedAt,
    status: "pending",
    mimeType: "audio/mp4",
    durationMs: 1_000,
    segments: [{ sequence: 0, durationMs: 1_000, blob: new Blob(["a"]) }],
  };
}

describe("IndexedDbSessionRepository", () => {
  it("ローカル保存を最大3セッションに制限する", async () => {
    const repository = new IndexedDbSessionRepository(new IDBFactory());
    await repository.put(session("a", 1));
    await repository.put(session("b", 2));
    await repository.put(session("c", 3));

    await expect(repository.put(session("d", 4))).rejects.toThrow("3件");
    expect(await repository.list()).toHaveLength(3);
  });

  it("最終更新から24時間以上経過した音声を削除する", async () => {
    const repository = new IndexedDbSessionRepository(new IDBFactory());
    await repository.put(session("expired", 1_000));
    await repository.put(session("active", 2_000));

    const removed = await repository.cleanup(1_000 + SESSION_TTL_MS);

    expect(removed).toEqual(["expired"]);
    expect(
      (await repository.list()).map((item) => item.clientSessionId),
    ).toEqual(["active"]);
  });
});
