import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";

import ProcessingStatus from "./ProcessingStatus.svelte";
import type { ProcessingProgress } from "./session-status";

const recordId = "11111111-1111-4111-8111-111111111111";
function progress(
  changes: Partial<ProcessingProgress> = {},
): ProcessingProgress {
  return {
    status: "queued",
    totalSegments: 2,
    processedSegments: 0,
    failedSegments: 0,
    recordId: null,
    incomplete: false,
    ...changes,
  };
}

function props() {
  return {
    progress: progress(),
    issue: null,
    loading: false,
    paused: false,
    onRefresh: vi.fn(),
  };
}

describe("ProcessingStatus", () => {
  it("待機と処理中の進捗を読み上げ領域で更新する", async () => {
    const options = props();
    const { rerender } = render(ProcessingStatus, options);
    expect(screen.getByRole("status")).toHaveTextContent("ワーカー待ち");
    await rerender({
      ...options,
      progress: progress({ status: "processing", processedSegments: 1 }),
    });
    expect(screen.getByRole("status")).toHaveTextContent("1/2区間完了");
    await fireEvent.click(
      screen.getByRole("button", { name: "状態を再確認する" }),
    );
    expect(options.onRefresh).toHaveBeenCalledOnce();
  });

  it("完了後は記録へのリンクと承認前に配信しない案内を表示する", () => {
    render(ProcessingStatus, {
      ...props(),
      progress: progress({
        status: "completed",
        recordId,
        processedSegments: 2,
      }),
    });
    expect(
      screen.getByRole("link", { name: "作成された記録を確認する" }),
    ).toHaveAttribute("href", `/teacher/review/${recordId}/`);
    expect(screen.getByText(/承認するまで配信されません/)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "状態を再確認する" }),
    ).not.toBeInTheDocument();
  });

  it("部分失敗は内容の抜け漏れを確認するよう警告する", () => {
    render(ProcessingStatus, {
      ...props(),
      progress: progress({
        status: "completed",
        recordId,
        incomplete: true,
        failedSegments: 1,
      }),
    });
    expect(screen.getByText(/記録には抜けがある可能性/)).toBeInTheDocument();
  });

  it("候補がない完了を失敗として案内しない", () => {
    render(ProcessingStatus, {
      ...props(),
      progress: progress({ status: "completed", processedSegments: 2 }),
    });
    expect(
      screen.getByText(/記録の候補は作成されませんでした/),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "作成された記録を確認する" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/録音し直すか/)).not.toBeInTheDocument();
  });

  it.each(["failed", "expired"] as const)(
    "%s時に再録音や手入力を案内する",
    (status) => {
      render(ProcessingStatus, { ...props(), progress: progress({ status }) });
      expect(screen.getByText(/途中再開はできません/)).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: /送信/ }),
      ).not.toBeInTheDocument();
    },
  );

  it("通信失敗時も最後に取得した進捗を残す", () => {
    render(ProcessingStatus, {
      ...props(),
      progress: progress({ status: "processing", processedSegments: 1 }),
      issue: "connection",
    });
    expect(screen.getByRole("status")).toHaveTextContent("1/2区間完了");
    expect(screen.getByText(/自動で再試行します/)).toBeInTheDocument();
  });

  it.each([{ loading: true }, { paused: true }])(
    "取得中やオフライン中は手動確認を無効にする: %j",
    (changes) => {
      render(ProcessingStatus, { ...props(), ...changes });
      expect(
        screen.getByRole("button", { name: "状態を再確認する" }),
      ).toBeDisabled();
    },
  );

  it("権限や機能の無効化は無限待ちにせず案内する", () => {
    render(ProcessingStatus, {
      ...props(),
      progress: null,
      issue: "unavailable",
    });
    expect(screen.getByRole("status")).toHaveTextContent(
      "処理状況を確認できません",
    );
    expect(
      screen.queryByRole("button", { name: "状態を再確認する" }),
    ).not.toBeInTheDocument();
  });
});
