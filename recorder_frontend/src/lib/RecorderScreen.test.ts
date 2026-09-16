import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";

import RecorderScreen from "./RecorderScreen.svelte";

describe("RecorderScreen", () => {
  it("受付後に進捗・結果リンクと待機へ戻る操作を表示する", () => {
    const recordId = "11111111-1111-4111-8111-111111111111";
    render(RecorderScreen, {
      view: "accepted",
      processing: {
        status: "completed",
        totalSegments: 2,
        processedSegments: 2,
        failedSegments: 0,
        recordId,
        incomplete: false,
      },
    });
    expect(screen.getByRole("status")).toHaveTextContent("2/2区間完了");
    expect(
      screen.getByRole("link", { name: "作成された記録を確認する" }),
    ).toHaveAttribute("href", `/teacher/review/${recordId}/`);
    expect(
      screen.getByRole("button", { name: "録音待機へ戻る" }),
    ).toBeInTheDocument();
  });

  it("初回確認後に録音開始操作を表示する", async () => {
    const onConfirmCaution = vi.fn();
    const { rerender } = render(RecorderScreen, {
      view: "ready",
      cautionConfirmed: false,
      onConfirmCaution,
    });
    await fireEvent.click(screen.getByRole("button", { name: "確認しました" }));
    expect(onConfirmCaution).toHaveBeenCalledOnce();

    await rerender({ view: "ready", cautionConfirmed: true });
    expect(
      screen.getByRole("button", { name: /録音開始/ }),
    ).toBeInTheDocument();
  });

  it("録音中は文言・時間・一時停止・停止を表示する", () => {
    render(RecorderScreen, { view: "recording", elapsedMs: 65_000 });
    expect(screen.getByText("録音中")).toBeInTheDocument();
    expect(screen.getByLabelText("録音時間 01:05")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "一時停止" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "録音を停止" }),
    ).toBeInTheDocument();
  });

  it("停止後は再生を設けず送信と破棄だけを表示する", () => {
    render(RecorderScreen, {
      view: "stopped",
      elapsedMs: 1_000,
      segmentCount: 1,
    });
    expect(
      screen.getByRole("button", { name: "送信する" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "破棄する" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /再生/ }),
    ).not.toBeInTheDocument();
  });

  it("別録音者の未送信データの詳細を隠す", () => {
    render(RecorderScreen, {
      view: "unsent",
      foreignSessionExists: true,
      ownedSessions: [],
    });
    expect(screen.getByText(/元の録音者がログイン/)).toBeInTheDocument();
  });
});
