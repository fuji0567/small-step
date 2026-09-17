import { fireEvent, render, screen } from "@testing-library/svelte";
import { tick } from "svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App.svelte";
import type { LocalRecordingSession } from "./lib/types";

const fixtures = vi.hoisted(() => ({
  sessions: new Map<string, LocalRecordingSession>(),
}));
vi.mock("./lib/storage", async (original) => {
  const module = await original<typeof import("./lib/storage")>();
  return {
    ...module,
    IndexedDbSessionRepository: class {
      async list() {
        return [...fixtures.sessions.values()];
      }
      async put(session: LocalRecordingSession) {
        fixtures.sessions.set(session.clientSessionId, session);
      }
      async delete(id: string) {
        fixtures.sessions.delete(id);
      }
      async cleanup() {
        return [];
      }
    },
  };
});

async function settle() {
  await vi.advanceTimersByTimeAsync(0);
  for (let i = 0; i < 30; i++) await Promise.resolve();
  await vi.advanceTimersByTimeAsync(0);
  await tick();
}

describe("App continuous recording", () => {
  let stopTrack: ReturnType<typeof vi.fn>;
  let getUserMedia: ReturnType<typeof vi.fn>;
  let fetchFn: ReturnType<typeof vi.fn>;
  let unauthorized: boolean;
  const servers = new Map<
    string,
    {
      id: string;
      status: string;
      segments: unknown[];
      client_session_id: string;
      total_duration_ms: number;
    }
  >();

  beforeEach(() => {
    vi.useFakeTimers();
    fixtures.sessions.clear();
    servers.clear();
    unauthorized = false;
    sessionStorage.clear();
    localStorage.clear();
    sessionStorage.setItem("small-step.access-token", "test-token");
    localStorage.setItem("small-step.recorder-caution-confirmed", "yes");
    Object.defineProperty(document, "visibilityState", {
      value: "visible",
      configurable: true,
    });
    Object.defineProperty(navigator, "onLine", {
      value: true,
      configurable: true,
    });
    stopTrack = vi.fn();
    const track = {
      stop: stopTrack,
      readyState: "live",
      muted: false,
      addEventListener: vi.fn(),
    };
    getUserMedia = vi.fn(async () => ({
      getTracks: () => [track],
      getAudioTracks: () => [track],
    }));
    Object.defineProperty(navigator, "mediaDevices", {
      value: { getUserMedia },
      configurable: true,
    });
    vi.stubGlobal(
      "MediaRecorder",
      class {
        static isTypeSupported() {
          return true;
        }
        state = "inactive";
        ondataavailable: ((event: BlobEvent) => void) | null = null;
        onstop: ((event: Event) => void) | null = null;
        start() {
          this.state = "recording";
        }
        stop() {
          this.state = "inactive";
          this.ondataavailable?.({
            data: new Blob(["test audio"], { type: "audio/mp4" }),
          } as BlobEvent);
          this.onstop?.(new Event("stop"));
        }
      },
    );
    fetchFn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      const json = (body: unknown) =>
        new Response(JSON.stringify(body), {
          headers: { "Content-Type": "application/json" },
        });
      if (path === "/api/v1/auth/config")
        return json({ auth_mode: "supabase" });
      if (path === "/api/v1/auth/me")
        return json({ id: "teacher", name: "Test teacher", role: "teacher" });
      if (unauthorized) return new Response(null, { status: 401 });
      if (path === "/api/v1/recorder/sessions" && init?.method === "POST") {
        const clientId = JSON.parse(init.body as string)
          .client_session_id as string;
        const server = {
          id: clientId,
          client_session_id: clientId,
          status: "draft",
          segments: [],
          total_duration_ms: 60_000,
        };
        servers.set(clientId, server);
        return json(server);
      }
      const id = path.split("/")[5]!;
      const server = servers.get(id)!;
      if (path.endsWith("/finalize")) server.status = "completed";
      return json(server);
    });
    vi.stubGlobal("fetch", fetchFn);
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("明示開始までマイクを開かず60秒ごとと停止時の端数を自動送信する", async () => {
    const { unmount } = render(App);
    await settle();
    expect(getUserMedia).not.toHaveBeenCalled();
    await fireEvent.click(
      screen.getByRole("button", { name: "連続録音・自動送信を開始" }),
    );
    await settle();
    await vi.advanceTimersByTimeAsync(60_000);
    await settle();
    expect(servers.size).toBe(1);
    expect(screen.getByText("録音中")).toBeInTheDocument();
    expect(fixtures.sessions.size).toBe(0);
    await vi.advanceTimersByTimeAsync(5_000);
    await fireEvent.click(screen.getByRole("button", { name: "録音を停止" }));
    await settle();
    expect(servers.size).toBe(2);
    expect(stopTrack).toHaveBeenCalled();
    expect(screen.getByText("録音を停止しました")).toBeInTheDocument();
    unmount();
  });

  it("通信断では3区間で一時停止し復旧しても自動再開しない", async () => {
    const { unmount } = render(App);
    await settle();
    await fireEvent.click(
      screen.getByRole("button", { name: "連続録音・自動送信を開始" }),
    );
    await settle();
    Object.defineProperty(navigator, "onLine", {
      value: false,
      configurable: true,
    });
    await vi.advanceTimersByTimeAsync(180_000);
    await settle();
    expect(fixtures.sessions.size).toBe(3);
    expect(screen.getByText("一時停止中")).toBeInTheDocument();
    Object.defineProperty(navigator, "onLine", {
      value: true,
      configurable: true,
    });
    window.dispatchEvent(new Event("online"));
    await settle();
    expect(screen.getByText("一時停止中")).toBeInTheDocument();
    unmount();
  });

  it("録音中の認証切れでマイクを停止しログインへ戻る", async () => {
    const { unmount } = render(App);
    await settle();
    await fireEvent.click(
      screen.getByRole("button", { name: "連続録音・自動送信を開始" }),
    );
    await settle();
    unauthorized = true;
    await vi.advanceTimersByTimeAsync(60_000);
    await settle();
    expect(stopTrack).toHaveBeenCalled();
    expect(screen.getByText("先生ログイン")).toBeInTheDocument();
    expect(fixtures.sessions.size).toBe(1);
    unmount();
  });

  it("画面が背面になれば端数を確定し前面復帰しても再開しない", async () => {
    const { unmount } = render(App);
    await settle();
    await fireEvent.click(
      screen.getByRole("button", { name: "連続録音・自動送信を開始" }),
    );
    await settle();
    await vi.advanceTimersByTimeAsync(10_000);
    Object.defineProperty(document, "visibilityState", {
      value: "hidden",
      configurable: true,
    });
    document.dispatchEvent(new Event("visibilitychange"));
    await settle();
    expect(screen.getByText("一時停止中")).toBeInTheDocument();
    Object.defineProperty(document, "visibilityState", {
      value: "visible",
      configurable: true,
    });
    document.dispatchEvent(new Event("visibilitychange"));
    await settle();
    expect(screen.getByText("一時停止中")).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: "録音を再開" }));
    await settle();
    expect(screen.getByText("録音中")).toBeInTheDocument();
    unmount();
  });

  it("画面の破棄でマイクを解放し保存済みデータの再送は次回起動に任せる", async () => {
    const { unmount } = render(App);
    await settle();
    await fireEvent.click(
      screen.getByRole("button", { name: "連続録音・自動送信を開始" }),
    );
    await settle();
    await vi.advanceTimersByTimeAsync(10_000);
    unmount();
    await settle();
    expect(stopTrack).toHaveBeenCalled();
    expect(fixtures.sessions.size).toBe(1);
    expect(servers.size).toBe(0);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(servers.size).toBe(0);
  });

  it("手動モードは停止まで自動送信せず送信操作後に受付する", async () => {
    const { unmount } = render(App);
    await settle();
    await fireEvent.click(screen.getByRole("checkbox", { name: /連続録音/ }));
    await fireEvent.click(screen.getByRole("button", { name: "録音開始" }));
    await settle();
    await vi.advanceTimersByTimeAsync(65_000);
    await fireEvent.click(screen.getByRole("button", { name: "録音を停止" }));
    await settle();
    expect(servers.size).toBe(0);
    expect(fixtures.sessions.size).toBe(1);
    await fireEvent.click(screen.getByRole("button", { name: "送信する" }));
    await settle();
    expect(servers.size).toBe(1);
    expect(fixtures.sessions.size).toBe(0);
    expect(screen.getByText("受付が完了しました")).toBeInTheDocument();
    unmount();
  });
});
