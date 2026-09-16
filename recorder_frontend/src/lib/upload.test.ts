import { describe, expect, it, vi } from "vitest";

import type { RecorderApi } from "./api";
import type { SessionRepository } from "./storage";
import type { LocalRecordingSession } from "./types";
import { sha256, UploadCoordinator } from "./upload";

function localSession(): LocalRecordingSession {
  return {
    clientSessionId: "client-1",
    serverSessionId: "server-1",
    ownerId: "teacher-1",
    createdAt: 1,
    updatedAt: 1,
    status: "pending",
    mimeType: "audio/mp4",
    durationMs: 2_000,
    segments: [
      {
        sequence: 0,
        durationMs: 2_000,
        blob: new Blob(["hello"], { type: "audio/mp4" }),
      },
    ],
  };
}

function repository(): SessionRepository {
  return {
    list: vi.fn(async () => []),
    put: vi.fn(async () => undefined),
    delete: vi.fn(async () => undefined),
    cleanup: vi.fn(async () => []),
  };
}

describe("UploadCoordinator", () => {
  it("SHA-256・録音時間・fileをmultipartで送る", async () => {
    const uploadSegment = vi.fn(async () => null);
    const api = {
      getSession: vi.fn(async () => ({
        id: "server-1",
        client_session_id: "client-1",
        status: "draft",
        segments: [],
        total_duration_ms: 0,
      })),
      uploadSegment,
      finalize: vi.fn(async () => null),
    } as unknown as RecorderApi;
    const store = repository();
    const serverId = await new UploadCoordinator({
      api,
      repository: store,
    }).upload(localSession());

    const calls = uploadSegment.mock.calls as unknown as [
      string,
      number,
      FormData,
    ][];
    const form = calls[0]![2];
    expect(form.get("duration_ms")).toBe("2000");
    expect(form.get("sha256")).toBe(await sha256(new Blob(["hello"])));
    expect(form.get("file")).toBeInstanceOf(Blob);
    expect(store.delete).toHaveBeenCalledWith("client-1");
    expect(serverId).toBe("server-1");
  });

  it("サーバー受信済みの同一セグメントを再送しない", async () => {
    const session = localSession();
    const hash = await sha256(session.segments[0]!.blob);
    const uploadSegment = vi.fn(async () => null);
    const api = {
      getSession: vi.fn(async () => ({
        id: "server-1",
        client_session_id: "client-1",
        status: "draft",
        segments: [
          {
            sequence: 0,
            duration_ms: 2_000,
            size_bytes: session.segments[0]!.blob.size,
            sha256: hash,
            media_type: "audio/mp4",
          },
        ],
        total_duration_ms: 2_000,
      })),
      uploadSegment,
      finalize: vi.fn(async () => null),
    } as unknown as RecorderApi;

    await new UploadCoordinator({ api, repository: repository() }).upload(
      session,
    );
    expect(uploadSegment).not.toHaveBeenCalled();
  });

  it("finalize成功応答を失ってもqueuedならローカル音声を削除する", async () => {
    const store = repository();
    const api = {
      getSession: vi.fn(async () => ({
        id: "server-1",
        client_session_id: "client-1",
        status: "queued",
        segments: [],
        total_duration_ms: 2_000,
      })),
      uploadSegment: vi.fn(),
      finalize: vi.fn(),
    } as unknown as RecorderApi;

    const serverId = await new UploadCoordinator({
      api,
      repository: store,
    }).upload(localSession());

    expect(api.uploadSegment).not.toHaveBeenCalled();
    expect(api.finalize).not.toHaveBeenCalled();
    expect(serverId).toBe("server-1");
    expect(store.delete).toHaveBeenCalledWith("client-1");
  });

  it("自動再送は送信開始済みのセッションだけを対象にする", async () => {
    const sessions = [
      localSession(),
      {
        ...localSession(),
        clientSessionId: "recording",
        status: "recording" as const,
      },
      {
        ...localSession(),
        clientSessionId: "uploading",
        status: "uploading" as const,
      },
    ];
    const store = repository();
    vi.mocked(store.list).mockResolvedValue(sessions);
    const api = {
      getSession: vi.fn(async () => ({
        id: "server-1",
        client_session_id: "client-1",
        status: "queued",
        segments: [],
        total_duration_ms: 2_000,
      })),
      uploadSegment: vi.fn(),
      finalize: vi.fn(),
    } as unknown as RecorderApi;

    const result = await new UploadCoordinator({
      api,
      repository: store,
    }).retryOwned("teacher-1");

    expect(result.attempted).toBe(1);
    expect(api.getSession).toHaveBeenCalledOnce();
  });
});
