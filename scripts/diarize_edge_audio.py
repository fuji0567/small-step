"""Show anonymous speaker intervals for one local edge-audio file."""

from __future__ import annotations

import argparse

from app.config import Settings
from app.edge_audio import EdgeAudioProcessor, EdgeAudioError
from app.speaker_diarization import PyannoteCommunityDiarizer, SpeakerDiarizationError


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ローカル音声を匿名の話者区間へ分けます。音声や文字起こしは送信・保存しません。"
    )
    parser.add_argument("audio_path", help="EDGE_AUDIO_INBOX_DIR 内にある音声ファイル")
    args = parser.parse_args()

    settings = Settings()
    try:
        audio_path = EdgeAudioProcessor(settings=settings)._resolve_audio_path(args.audio_path)
        diarizer = PyannoteCommunityDiarizer(
            model=settings.speaker_diarization_model,
            token=settings.speaker_diarization_token,
            device=settings.speaker_diarization_device,
            batch_size=settings.speaker_diarization_batch_size,
            low_volume_retry=settings.speaker_diarization_low_volume_retry,
        )
        result = diarizer.diarize(audio_path)
    except (EdgeAudioError, SpeakerDiarizationError) as error:
        raise SystemExit(str(error)) from error

    print(f"匿名の話者数: {result.speaker_count}")
    if result.low_volume_retry_speaker_count is not None:
        print(f"音量差を補正して再確認した話者数: {result.low_volume_retry_speaker_count}")
    if result.used_low_volume_retry:
        print("補正後の結果を採用しています。")
    for segment in result.segments:
        print(f"{segment.start_seconds:.1f}s - {segment.end_seconds:.1f}s: {segment.speaker_label}")


if __name__ == "__main__":
    main()
