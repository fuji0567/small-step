import { fireEvent, render, screen } from "@testing-library/svelte";
import { tick } from "svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import RecorderDemoView from "./RecorderDemoView.svelte";
import { RecorderApiError } from "./api";
import type { RecorderDemo } from "./types";

const transcript =
  "speaker_01: 架空の園児が積み木を5つ積めたね。<script>secret</script>";
function result(): RecorderDemo {
  return {
    outcome: "record_created",
    expires_at: Date.now() / 1000 + 300,
    record_id: "11111111-1111-4111-8111-111111111111",
    events: [
      {
        phase: "音声区間 1",
        kind: "transcript",
        text: transcript,
        truncated: false,
      },
      {
        phase: "音声区間 1",
        kind: "llm_output",
        text: '{"recordable":true}',
        truncated: false,
      },
    ],
  };
}
async function open() {
  await fireEvent.click(
    screen.getByRole("button", { name: "直近の録音の処理内容を表示" }),
  );
  await tick();
}

describe("RecorderDemoView", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    Object.defineProperty(document, "visibilityState", {
      value: "visible",
      configurable: true,
    });
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("明示操作まで内容を取得せず実際の文字をHTMLとして実行しない", async () => {
    const api = { getDemo: vi.fn(async () => result()) };
    const { container } = render(RecorderDemoView, {
      sessionId: "session",
      api,
      onAuthenticationError: vi.fn(),
    });
    expect(api.getDemo).not.toHaveBeenCalled();
    await open();
    expect(screen.getByText(transcript)).toBeInTheDocument();
    expect(container.querySelector("script")).toBeNull();
    expect(
      screen.getByRole("link", { name: /先生が確認する/ }),
    ).toHaveAttribute(
      "href",
      "/teacher/review/11111111-1111-4111-8111-111111111111/",
    );
    await fireEvent.click(screen.getByRole("button", { name: "内容を隠す" }));
    expect(screen.queryByText(transcript)).not.toBeInTheDocument();
  });

  it("表示期限になれば画面から消し取得を停止する", async () => {
    const response = { ...result(), expires_at: Date.now() / 1000 + 2 };
    const api = { getDemo: vi.fn(async () => response) };
    render(RecorderDemoView, {
      sessionId: "session",
      api,
      onAuthenticationError: vi.fn(),
    });
    await open();
    await vi.advanceTimersByTimeAsync(3000);
    expect(screen.queryByText(transcript)).not.toBeInTheDocument();
    expect(screen.getByText(/表示期限が切れたため/)).toBeInTheDocument();
    expect(api.getDemo).toHaveBeenCalledOnce();
  });

  it("非表示後に遅れて届いた応答を表示しない", async () => {
    let resolve!: (value: RecorderDemo) => void;
    const api = {
      getDemo: vi.fn<
        (id: string, signal?: AbortSignal) => Promise<RecorderDemo>
      >(
        () =>
          new Promise<RecorderDemo>((done) => {
            resolve = done;
          }),
      ),
    };
    render(RecorderDemoView, {
      sessionId: "session",
      api,
      onAuthenticationError: vi.fn(),
    });
    await open();
    Object.defineProperty(document, "visibilityState", {
      value: "hidden",
      configurable: true,
    });
    document.dispatchEvent(new Event("visibilitychange"));
    resolve(result());
    await tick();
    expect(screen.queryByText(transcript)).not.toBeInTheDocument();
    expect(api.getDemo.mock.calls[0][1]?.aborted).toBe(true);
  });

  it("権限・認証が失われたら表示済みの内容も消す", async () => {
    const error = new RecorderApiError(401, "expired");
    const api = {
      getDemo: vi
        .fn()
        .mockResolvedValueOnce(result())
        .mockRejectedValueOnce(error),
    };
    const onAuthenticationError = vi.fn();
    render(RecorderDemoView, {
      sessionId: "session",
      api,
      onAuthenticationError,
    });
    await open();
    await vi.advanceTimersByTimeAsync(5000);
    expect(screen.queryByText(transcript)).not.toBeInTheDocument();
    expect(onAuthenticationError).toHaveBeenCalledWith(error);
  });
});
