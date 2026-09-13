"""Upload one audio file and verify VRT processing without approving it."""

from __future__ import annotations

import argparse
import getpass
import sys

from app.config import Settings
from app.models import CloudAudioJobStatus
from app.vrt_pipeline_verifier import (
    VrtPipelineVerificationError,
    VrtPipelineVerifier,
    validate_verification_audio,
)


STATUS_LABELS = {
    CloudAudioJobStatus.queued: "受付済み",
    CloudAudioJobStatus.processing: "GPU処理中",
    CloudAudioJobStatus.completed: "処理完了",
    CloudAudioJobStatus.failed: "処理失敗",
    CloudAudioJobStatus.expired: "期限切れ",
}


def main() -> None:
    settings = Settings()
    parser = argparse.ArgumentParser(
        description=(
            "音声1件をVRTへ送り、GPU処理と承認待ち候補の作成まで確認します。"
            "先生の承認やLINE送信は行いません。"
        )
    )
    parser.add_argument("audio_path", help="確認に使う音声ファイル")
    parser.add_argument(
        "--api-url",
        default=settings.edge_api_url,
        help="VRTのHTTPS URL、またはSSH転送中のhttp://127.0.0.1",
    )
    parser.add_argument("--child-id", help="特定園児の確認時だけUUIDを指定", default=None)
    parser.add_argument("--timeout-seconds", type=float, default=900.0)
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args()

    api_key = settings.edge_api_key or getpass.getpass(
        "録音端末キー（画面には表示されません）: "
    )
    audio_path = validate_verification_audio(
        args.audio_path,
        max_file_bytes=settings.edge_audio_max_file_bytes,
    )
    verifier = VrtPipelineVerifier(
        api_url=args.api_url,
        api_key=api_key or "",
        request_timeout_seconds=settings.edge_api_timeout_seconds,
    )
    try:
        verifier.verify_readiness()
        print("1/4 VRTのGPU音声処理: 準備完了")
        verifier.verify_device()
        print("2/4 録音端末キー: 有効")
        initial = verifier.upload(audio_path=audio_path, child_id=args.child_id)
        print("3/4 音声アップロード: 受付済み（元ファイルは保持）")
        result = verifier.wait_for_completion(
            initial,
            timeout_seconds=args.timeout_seconds,
            poll_seconds=args.poll_seconds,
            on_status=lambda status: print(f"    VRT状態: {STATUS_LABELS[status]}"),
        )
    finally:
        verifier.close()

    if result.status == CloudAudioJobStatus.completed and result.created_candidate:
        print("4/4 GPU処理: 承認待ちの記録候補を作成しました。LINE送信はしていません。")
        return
    if result.status == CloudAudioJobStatus.completed:
        print("4/4 GPU処理: 正常完了しました。具体的な出来事がないため記録対象外です。")
        return
    if result.status == CloudAudioJobStatus.failed:
        raise VrtPipelineVerificationError(
            "GPU処理に失敗しました。先生画面の「音声処理」で状態を確認してください。"
        )
    raise VrtPipelineVerificationError(
        "音声ジョブが処理前に期限切れになりました。GPUワーカーの稼働状態を確認してください。"
    )


if __name__ == "__main__":
    try:
        main()
    except VrtPipelineVerificationError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
    except KeyboardInterrupt:
        print("\n確認を中止しました。アップロード済みのジョブはVRT上で処理を継続します。", file=sys.stderr)
        raise SystemExit(130)
