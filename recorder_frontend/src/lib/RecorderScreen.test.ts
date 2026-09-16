import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";

import RecorderScreen from "./RecorderScreen.svelte";

describe("RecorderScreen", () => {
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
