"""Compare baseline/tuned prompts on fictional cases, without API/DB/LINE writes."""

import argparse
import json
from pathlib import Path

from app.config import Settings
from app.edge_audio import OpenAICompatibleSummarizer
from app.llm_guidance import GUIDANCE_VERSION
from app.llm_guidance_evaluation import CASES, EVALUATION_VERSION, GuidanceCase, evaluate_guidance


def review_candidate(case: GuidanceCase, candidate) -> bool:
    print(f"\n{case.case_id} 確認基準: {case.review_points}")
    print("架空の会話:", case.transcript)
    if case.prior_context:
        print("架空の過去記録:", case.prior_context)
    print("候補:", json.dumps(candidate.model_dump(mode="json"), ensure_ascii=False))
    while True:
        answer = input("事実・人物関係・尊厳・家庭への表現が妥当ですか [y/n]: ").strip().lower()
        if answer in {"y", "n"}:
            return answer == "y"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="架空の会話32件でLLMの指示を評価します。記録作成・LINE送信はしません。")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--list", action="store_true", help="評価例だけ表示。通信しません")
    mode.add_argument("--run", action="store_true", help="設定したLLMで実際に推論")
    parser.add_argument("--baseline", action="store_true", help="ヒアリング指示追加前の指示で比較")
    parser.add_argument("--review", action="store_true", help="架空の入力と候補を表示して人手評価")
    parser.add_argument("--base-url", help="LLMのOpenAI互換URL")
    parser.add_argument("--allow-external-llm", action="store_true", help="ループバック以外のLLMへの通信を明示許可")
    parser.add_argument("--report", help="本文を含まない集計結果の保存先（既定は変更前・調整版で分離）")
    args = parser.parse_args(argv)
    if args.list:
        for case in CASES:
            print(f"{case.case_id}: {case.transcript}\n  期待: {case.category or '対象外'} / {case.review_points}")
        return 0
    try:
        settings = Settings()
    except Exception:
        print("評価を開始できません。環境設定を確認してください。秘密値や設定の詳細は表示しません。")
        return 2
    summarizer = OpenAICompatibleSummarizer(
        base_url=args.base_url or settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        # Do not inherit production external opt-in for an evaluation command.
        allow_external=args.allow_external_llm,
        timeout_seconds=settings.llm_timeout_seconds,
        backend=settings.llm_backend,
        guidance_enabled=not args.baseline,
    )
    try:
        summarizer._validate_endpoint()
    except Exception:
        print("評価を開始できません。LLMのURL・モデルと、外部通信の明示許可を確認してください。")
        return 2
    report = evaluate_guidance(summarizer, reviewer=review_candidate if args.review else None)
    report["guidance_version"] = "baseline" if args.baseline else GUIDANCE_VERSION
    report["evaluation_version"] = EVALUATION_VERSION
    report["llm_backend"] = settings.llm_backend
    report["model"] = settings.llm_model
    path = Path(args.report or (
        "data/llm-guidance-baseline.json" if args.baseline else "data/llm-guidance-tuned.json"
    ))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"評価: {report['classification_passed']}/{report['total']}件 分類一致 / エラー {report['errors']}件")
    print(f"誤検出: {report['false_positives']}件 / 見逃し: {report['missed']}件")
    print("自動チェック:", "合格" if report["automatic_checks_passed"] else "要確認")
    if report["human_review_complete"]:
        print(f"人手合格: {report['human_approved']}/{report['total']}件")
    print("人手評価:", "完了" if report["human_review_complete"] else "未完了（文章品質の合格を意味しません）")
    print("本文なし集計:", path)
    return 0 if report["automatic_checks_passed"] and (
        not args.review or report["human_approved"] == report["total"]
    ) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n評価を中止しました。記録作成・送信はしていません。")
        raise SystemExit(130)
