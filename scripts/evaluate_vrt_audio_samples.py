"""Evaluate multiple anonymous audio samples against the live VRT pipeline."""

from __future__ import annotations

import argparse
import getpass
import sys

from app.config import Settings
from app.vrt_audio_evaluation import (
    build_evaluation_report,
    evaluate_audio_cases,
    load_evaluation_manifest,
    write_evaluation_report,
)
from app.vrt_pipeline_verifier import VrtPipelineVerificationError, VrtPipelineVerifier


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
    args = parser.parse_args()

    cases = load_evaluation_manifest(args.manifest)
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
            cases=cases,
            max_file_bytes=settings.edge_audio_max_file_bytes,
            timeout_seconds=args.timeout_seconds,
            poll_seconds=args.poll_seconds,
            on_case_start=lambda index, total, case_id: print(
                f"{index}/{total} 評価中: {case_id}"
            ),
        )
    finally:
        verifier.close()

    report = build_evaluation_report(results)
    output_path = write_evaluation_report(args.report, report)
    summary = report["summary"]
    print(
        f"評価完了: 合格={summary['passed']}件 / "
        f"要確認={summary['failed']}件 / 合計={summary['total']}件"
    )
    print(f"匿名集計レポート: {output_path}")
    if summary["failed"]:
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
