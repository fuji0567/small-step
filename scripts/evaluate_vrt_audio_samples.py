"""Evaluate multiple anonymous audio samples against the live VRT pipeline."""

from __future__ import annotations

import argparse
import getpass
import sys

from app.config import Settings
from app.vrt_audio_evaluation import (
    VrtAudioHumanReview,
    build_evaluation_report,
    evaluate_audio_cases,
    load_evaluation_plan,
    write_evaluation_report,
)
from app.vrt_pipeline_verifier import VrtPipelineVerificationError, VrtPipelineVerifier


def ask_yes_no(prompt: str) -> bool:
    while True:
        answer = input(f"{prompt} [y/n]: ").strip().lower()
        if answer in {"y", "yes", "1", "はい"}:
            return True
        if answer in {"n", "no", "0", "いいえ"}:
            return False
        print("yまたはnを入力してください。")


def format_rate(value: float | None) -> str:
    return f"{value:.1%}" if value is not None else "未評価"


def review_candidate(case_id: str, category) -> VrtAudioHumanReview:
    category_label = {
        "growth": "成長記録",
        "injury": "怪我記録",
    }.get(category.value if category is not None else None, "分類なし")
    print(f"{case_id}: 先生画面の最新候補を確認してください（{category_label}）。")
    return VrtAudioHumanReview(
        summary_acceptable=ask_yes_no(
            "要約は音声に忠実で、保護者へ伝える候補として妥当ですか"
        ),
        conversation_prompt_acceptable=ask_yes_no(
            "会話のきっかけは、保護者が自然に話せる内容ですか"
        ),
    )


def main() -> None:
    settings = Settings()
    parser = argparse.ArgumentParser(
        description=(
            "複数のテスト音声について話者数と記録対象判定を確認します。"
            "レポートに音声、文字起こし、ファイル名、人物名は保存しません。"
        )
    )
    parser.add_argument("manifest", help="匿名のcase_idと期待値を記載したJSON")
    parser.add_argument(
        "--report",
        default="data/vrt-audio-evaluation-report.json",
        help="集計レポートの保存先",
    )
    parser.add_argument(
        "--api-url",
        default=settings.edge_api_url,
        help="VRTのHTTPS URL、またはSSH転送中のhttp://127.0.0.1",
    )
    parser.add_argument("--timeout-seconds", type=float, default=900.0)
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument(
        "--interactive-review",
        action="store_true",
        help="作成された候補を先生画面で確認し、生成文の合否を入力する",
    )
    args = parser.parse_args()

    plan = load_evaluation_plan(args.manifest)
    human_review_required = (
        plan.acceptance.min_summary_approval_rate is not None
        or plan.acceptance.min_conversation_prompt_approval_rate is not None
    )
    if human_review_required and not args.interactive_review:
        parser.error(
            "生成文の合格基準が設定されています。--interactive-reviewを付けて実行してください。"
        )
    api_key = settings.edge_api_key or getpass.getpass(
        "録音端末キー（画面には表示されません）: "
    )
    verifier = VrtPipelineVerifier(
        api_url=args.api_url,
        api_key=api_key or "",
        request_timeout_seconds=settings.edge_api_timeout_seconds,
    )
    try:
        results = evaluate_audio_cases(
            verifier=verifier,
            cases=plan.cases,
            max_file_bytes=settings.edge_audio_max_file_bytes,
            timeout_seconds=args.timeout_seconds,
            poll_seconds=args.poll_seconds,
            on_case_start=lambda index, total, case_id: print(
                f"{index}/{total} 評価中: {case_id}"
            ),
            review_candidate=review_candidate if args.interactive_review else None,
        )
    finally:
        verifier.close()

    report = build_evaluation_report(results, plan.acceptance)
    output_path = write_evaluation_report(args.report, report)
    summary = report["summary"]
    print(
        f"評価完了: ケース合格={summary['passed']}件 / "
        f"要確認={summary['failed']}件 / 合計={summary['total']}件"
    )
    print(
        f"話者数精度={summary['speaker_count_accuracy']:.1%} / "
        f"候補判定精度={summary['candidate_accuracy']:.1%} / "
        f"分類精度={summary['category_accuracy']:.1%}"
        if summary["category_accuracy"] is not None
        else (
            f"話者数精度={summary['speaker_count_accuracy']:.1%} / "
            f"候補判定精度={summary['candidate_accuracy']:.1%} / 分類精度=未評価"
        )
    )
    print(
        f"処理時間: 中央値={summary['elapsed_seconds']['p50']}秒 / "
        f"95%={summary['elapsed_seconds']['p95']}秒"
    )
    if summary["human_review"]["required"]:
        print(
            "人手確認: 要約="
            f"{format_rate(summary['human_review']['summary_approval_rate'])} / "
            "会話のきっかけ="
            f"{format_rate(summary['human_review']['conversation_prompt_approval_rate'])}"
        )
    print(f"総合判定: {'合格' if summary['overall_passed'] else '要調整'}")
    print(f"匿名集計レポート: {output_path}")
    if not summary["overall_passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    try:
        main()
    except VrtPipelineVerificationError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
    except KeyboardInterrupt:
        print("\n評価を中止しました。受付済みジョブはVRT上で処理を継続します。", file=sys.stderr)
        raise SystemExit(130)
