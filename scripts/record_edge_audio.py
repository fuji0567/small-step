"""Record short Mac microphone chunks into the local edge-audio inbox.

Completed chunks are atomically moved into the inbox. The watcher therefore
never reads a file while ffmpeg is still recording it.
"""

from __future__ import annotations

import argparse
import shutil

from app.config import Settings
from app.edge_recorder import list_audio_devices, record_one_chunk


def positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("0より大きい数値を指定してください。")
    return parsed


def main() -> None:
    settings = Settings()
    parser = argparse.ArgumentParser(
        description="Macのマイクを短いWAV音声としてローカル受信フォルダへ保存します。"
    )
    parser.add_argument("--list-devices", action="store_true", help="利用できるMacの音声入力を表示します。")
    parser.add_argument("--once", action="store_true", help="1つの録音だけ作成して終了します。")
    parser.add_argument(
        "--audio-device",
        default=settings.edge_audio_input_device,
        help="ffmpegの入力指定。例: :0。既定値は .env の EDGE_AUDIO_INPUT_DEVICE です。",
    )
    parser.add_argument(
        "--chunk-seconds",
        type=positive_float,
        default=settings.edge_audio_record_chunk_seconds,
        help="1ファイルの録音秒数。既定値は .env の EDGE_AUDIO_RECORD_CHUNK_SECONDS です。",
    )
    args = parser.parse_args()

    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise SystemExit("ffmpeg が見つかりません。Homebrewで ffmpeg をインストールしてください。")
    if args.list_devices:
        list_audio_devices(ffmpeg_bin)
        return

    print("Macのマイク録音を開始します。停止するには Control+C を押してください。")
    try:
        while True:
            record_one_chunk(
                ffmpeg_bin=ffmpeg_bin,
                audio_device=args.audio_device,
                chunk_seconds=args.chunk_seconds,
                inbox_dir=settings.edge_audio_inbox_dir,
            )
            print("録音済みの音声をローカル受信フォルダへ渡しました。")
            if args.once:
                return
    except KeyboardInterrupt:
        print("\nマイク録音を終了しました。")
    except RuntimeError as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
