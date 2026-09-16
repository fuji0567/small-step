"""Run the Small Step cloud GPU audio worker on a Sakura VRT instance."""

import argparse
import time
from contextlib import ExitStack
from datetime import timedelta

from app.cloud_audio import CloudAudioJobStorage
from app.cloud_audio_worker import process_next_cloud_audio_job
from app.config import Settings
from app.database import create_database_engine, create_session_factory, initialise_database
from app.edge_audio import EdgeAudioProcessor
from app.recorder import RecorderStorage
from app.recorder_worker import RecorderMaintenance, process_next_recorder_session
from app.speaker_diarization import PyannoteCommunityDiarizer
from app.worker_heartbeat import GPU_AUDIO_WORKER_NAME, RECORDER_AUDIO_WORKER_NAME, WorkerHeartbeatMonitor
from app.voiceprint import PyannoteVoiceprintExtractor
from app.voiceprint_quality import LocalVoiceprintQualityAnalyzer
from app.voiceprint_worker import process_next_voiceprint_job


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("1以上の整数を指定してください。")
    return parsed


def require_ready_configuration(settings: Settings, processor: EdgeAudioProcessor) -> None:
    if not settings.cloud_audio_enabled:
        raise SystemExit("CLOUD_AUDIO_ENABLED=true を設定してから起動してください。")
    status = processor.status()
    if not status["llm_configured"]:
        raise SystemExit("LLM_BASE_URL と LLM_MODEL を設定してから起動してください。")


def process_available_jobs(
    *,
    session_factory,
    storage: CloudAudioJobStorage,
    processor: EdgeAudioProcessor,
    limit: int,
    processing_timeout: timedelta,
) -> int:
    completed_count = 0
    for _ in range(limit):
        with session_factory() as db:
            job = process_next_cloud_audio_job(
                db=db,
                storage=storage,
                processor=processor,
                processing_timeout=processing_timeout,
            )
        if job is None:
            break
        completed_count += 1
        print(f"クラウド音声ジョブを処理しました: {job.id} ({job.status.value})")
    return completed_count


def process_available_voiceprint_jobs(
    *,
    session_factory,
    storage: CloudAudioJobStorage,
    extractor: PyannoteVoiceprintExtractor,
    quality_analyzer: LocalVoiceprintQualityAnalyzer,
    encryption_key: str,
    match_threshold: float,
    limit: int,
    processing_timeout: timedelta,
) -> int:
    completed_count = 0
    for _ in range(limit):
        with session_factory() as db:
            job = process_next_voiceprint_job(
                db=db,
                storage=storage,
                extractor=extractor,
                quality_analyzer=quality_analyzer,
                encryption_key=encryption_key,
                match_threshold=match_threshold,
                processing_timeout=processing_timeout,
            )
        if job is None:
            break
        completed_count += 1
        print(f"声紋ジョブを処理しました: {job.id} ({job.status.value})")
    return completed_count


def process_available_recorder_sessions(
    *, session_factory, storage: RecorderStorage, processor: EdgeAudioProcessor,
    processing_timeout: timedelta, max_duration_minutes: int, limit: int = 1,
) -> int:
    count = 0
    for _ in range(limit):
        with session_factory() as db:
            result = process_next_recorder_session(
                db=db, storage=storage, processor=processor,
                processing_timeout=processing_timeout, max_duration_minutes=max_duration_minutes,
            )
        if result is None:
            break
        count += 1
        print(f"録音セッションを処理しました ({result.status.value})")
    return count


def main() -> None:
    settings = Settings()
    parser = argparse.ArgumentParser(description="VRT上でクラウド音声ジョブをGPU処理します。")
    parser.add_argument("--once", action="store_true", help="現在のジョブを処理して終了します。")
    parser.add_argument("--limit", type=positive_int, default=10, help="1回に処理する最大件数です。")
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=settings.cloud_audio_worker_poll_seconds,
        help="待機秒数。既定値は CLOUD_AUDIO_WORKER_POLL_SECONDS です。",
    )
    args = parser.parse_args()
    if args.poll_seconds <= 0:
        raise SystemExit("--poll-seconds は0より大きい値にしてください。")

    processor = EdgeAudioProcessor(settings=settings)
    require_ready_configuration(settings, processor)
    storage = CloudAudioJobStorage(
        job_dir=settings.cloud_audio_job_dir,
        max_file_bytes=settings.edge_audio_max_file_bytes,
    )
    storage.ensure_directory()
    voiceprint_storage = None
    voiceprint_extractor = None
    voiceprint_quality_analyzer = None
    voiceprint_encryption_key = settings.voiceprint_encryption_key
    if settings.voiceprint_enabled:
        assert settings.speaker_diarization_token is not None
        assert voiceprint_encryption_key is not None
        voiceprint_storage = CloudAudioJobStorage(
            job_dir=settings.voiceprint_job_dir,
            max_file_bytes=settings.edge_audio_max_file_bytes,
        )
        voiceprint_storage.ensure_directory()
        voiceprint_extractor = PyannoteVoiceprintExtractor(
            model_name=settings.voiceprint_model,
            token=settings.speaker_diarization_token,
            device=settings.speaker_diarization_device,
        )
        voiceprint_quality_analyzer = LocalVoiceprintQualityAnalyzer(
            diarizer=PyannoteCommunityDiarizer(
                model=settings.speaker_diarization_model,
                token=settings.speaker_diarization_token,
                device=settings.speaker_diarization_device,
                low_volume_retry=False,
            )
        )

    engine = create_database_engine(settings.database_url)
    initialise_database(engine)
    session_factory = create_session_factory(engine)
    processing_timeout = timedelta(minutes=settings.cloud_audio_processing_timeout_minutes)
    voiceprint_processing_timeout = timedelta(
        minutes=settings.voiceprint_processing_timeout_minutes
    )
    recorder_storage = RecorderStorage(
        session_dir=settings.recorder_session_dir,
        max_segment_bytes=settings.recorder_max_segment_bytes,
    )
    recorder_processing_timeout = timedelta(minutes=settings.recorder_processing_timeout_minutes)
    contexts = ExitStack()
    try:
        if settings.recorder_enabled:
            recorder_storage.ensure_directory()
            contexts.enter_context(WorkerHeartbeatMonitor(
                session_factory=session_factory,
                worker_name=RECORDER_AUDIO_WORKER_NAME,
                interval_seconds=settings.worker_heartbeat_interval_seconds,
            ))
        # Cleanup keeps running while inference blocks, even after disabling uploads.
        contexts.enter_context(RecorderMaintenance(
            session_factory=session_factory, storage=recorder_storage,
            interval_seconds=settings.worker_heartbeat_interval_seconds,
            processing_timeout=recorder_processing_timeout,
            orphan_retention=timedelta(hours=settings.recorder_retention_hours),
        ))
        if args.once:
            count = process_available_jobs(
                session_factory=session_factory,
                storage=storage,
                processor=processor,
                limit=args.limit,
                processing_timeout=processing_timeout,
            )
            if (
                voiceprint_storage is not None
                and voiceprint_extractor is not None
                and voiceprint_quality_analyzer is not None
            ):
                count += process_available_voiceprint_jobs(
                    session_factory=session_factory,
                    storage=voiceprint_storage,
                    extractor=voiceprint_extractor,
                    quality_analyzer=voiceprint_quality_analyzer,
                    encryption_key=voiceprint_encryption_key,
                    match_threshold=settings.voiceprint_match_threshold,
                    limit=args.limit,
                    processing_timeout=voiceprint_processing_timeout,
                )
            if settings.recorder_enabled:
                count += process_available_recorder_sessions(
                    session_factory=session_factory, storage=recorder_storage,
                    processor=processor, processing_timeout=recorder_processing_timeout,
                    max_duration_minutes=settings.recorder_max_duration_minutes, limit=args.limit,
                )
            print(f"処理した音声ジョブ・録音セッション: {count}件")
            return

        with WorkerHeartbeatMonitor(
            session_factory=session_factory,
            worker_name=GPU_AUDIO_WORKER_NAME,
            interval_seconds=settings.worker_heartbeat_interval_seconds,
        ):
            while True:
                process_available_jobs(
                    session_factory=session_factory,
                    storage=storage,
                    processor=processor,
                    limit=args.limit,
                    processing_timeout=processing_timeout,
                )
                if (
                    voiceprint_storage is not None
                    and voiceprint_extractor is not None
                    and voiceprint_quality_analyzer is not None
                ):
                    process_available_voiceprint_jobs(
                        session_factory=session_factory,
                        storage=voiceprint_storage,
                        extractor=voiceprint_extractor,
                        quality_analyzer=voiceprint_quality_analyzer,
                        encryption_key=voiceprint_encryption_key,
                        match_threshold=settings.voiceprint_match_threshold,
                        limit=args.limit,
                        processing_timeout=voiceprint_processing_timeout,
                    )
                if settings.recorder_enabled:
                    process_available_recorder_sessions(
                        session_factory=session_factory, storage=recorder_storage,
                        processor=processor, processing_timeout=recorder_processing_timeout,
                        max_duration_minutes=settings.recorder_max_duration_minutes,
                    )
                time.sleep(args.poll_seconds)
    finally:
        contexts.close()
        engine.dispose()


if __name__ == "__main__":
    main()
