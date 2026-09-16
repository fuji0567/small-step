"""Shared, privacy-safe liveness tracking for background workers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import Event, Thread

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.models import WorkerHeartbeat, utc_now


GPU_AUDIO_WORKER_NAME = "gpu_audio"
RECORDER_AUDIO_WORKER_NAME = "recorder_audio"
LINE_DELIVERY_WORKER_NAME = "line_delivery"


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def record_worker_heartbeat(
    *,
    db: Session,
    worker_name: str,
    now: datetime | None = None,
) -> WorkerHeartbeat:
    """Insert or refresh one worker marker without storing job contents."""

    current_time = now or utc_now()
    updated = db.execute(
        update(WorkerHeartbeat)
        .where(WorkerHeartbeat.worker_name == worker_name)
        .values(last_seen_at=current_time)
    )
    if updated.rowcount == 0:
        db.add(WorkerHeartbeat(worker_name=worker_name, last_seen_at=current_time))
    try:
        db.commit()
    except IntegrityError:
        # Two copies can start together. If both attempted the first insert,
        # keep the row created by the winner and refresh its timestamp.
        db.rollback()
        db.execute(
            update(WorkerHeartbeat)
            .where(WorkerHeartbeat.worker_name == worker_name)
            .values(last_seen_at=current_time)
        )
        db.commit()
    heartbeat = db.get(WorkerHeartbeat, worker_name)
    if heartbeat is None:
        raise RuntimeError("Worker heartbeat was not persisted")
    return heartbeat


def worker_is_alive(
    *,
    db: Session,
    worker_name: str,
    stale_after: timedelta,
    now: datetime | None = None,
) -> bool:
    """Return whether a worker has refreshed its marker recently enough."""

    if stale_after <= timedelta():
        raise ValueError("stale_after must be positive")
    heartbeat = db.get(WorkerHeartbeat, worker_name)
    if heartbeat is None:
        return False
    return _as_utc(heartbeat.last_seen_at) >= _as_utc(now or utc_now()) - stale_after


class WorkerHeartbeatMonitor:
    """Keep a worker heartbeat fresh even while one job takes a long time."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        worker_name: str,
        interval_seconds: float,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        self.session_factory = session_factory
        self.worker_name = worker_name
        self.interval_seconds = interval_seconds
        self.stop_event = Event()
        self.thread: Thread | None = None

    def _pulse(self) -> None:
        with self.session_factory() as db:
            record_worker_heartbeat(db=db, worker_name=self.worker_name)

    def _run(self) -> None:
        while not self.stop_event.wait(self.interval_seconds):
            try:
                self._pulse()
            except Exception as error:
                # Keep the main worker alive; its normal database operation will
                # surface a persistent outage without exposing connection data.
                print(f"ワーカー稼働確認の更新に失敗しました（{type(error).__name__}）。")

    def __enter__(self) -> "WorkerHeartbeatMonitor":
        self._pulse()
        self.thread = Thread(
            target=self._run,
            name=f"{self.worker_name}-heartbeat",
            daemon=True,
        )
        self.thread.start()
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=min(self.interval_seconds + 1, 5))
