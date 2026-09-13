from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VRT_COMPOSE = ROOT / "compose.vrt.yaml"


def test_vrt_compose_manages_pinned_private_vllm_service():
    compose = VRT_COMPOSE.read_text(encoding="utf-8")

    assert "small-step-vllm:" in compose
    assert "vllm/vllm-openai:v0.11.0" in compose
    assert '"127.0.0.1:8001:8000"' in compose
    assert "VLLM_MODEL_CACHE_DIR" in compose
    assert "VLLM_COMPILE_CACHE_DIR" in compose
    assert "--disable-log-requests" in compose
    assert "restart: unless-stopped" in compose


def test_gpu_worker_waits_for_healthy_vllm():
    compose = VRT_COMPOSE.read_text(encoding="utf-8")
    gpu_worker = compose.split("  gpu-worker:", maxsplit=1)[1].split(
        "  line-worker:", maxsplit=1
    )[0]

    assert "small-step-vllm:" in gpu_worker
    assert "condition: service_healthy" in gpu_worker


def test_vllm_healthcheck_has_long_model_startup_grace_period():
    compose = VRT_COMPOSE.read_text(encoding="utf-8")
    vllm = compose.split("  small-step-vllm:", maxsplit=1)[1].split(
        "  api:", maxsplit=1
    )[0]

    assert "/health" in vllm
    assert "start_period: 300s" in vllm


def test_database_backup_tools_are_one_shot_and_restore_database_is_disposable():
    compose = VRT_COMPOSE.read_text(encoding="utf-8")
    database_tools = compose.split("  database-tools:", maxsplit=1)[1].split(
        "  restore-db:", maxsplit=1
    )[0]
    restore_db = compose.split("  restore-db:", maxsplit=1)[1].split(
        "volumes:", maxsplit=1
    )[0]

    assert "Dockerfile.database-tools" in database_tools
    assert "DATABASE_BACKUP_HOST_DIR" in database_tools
    assert "no-new-privileges:true" in database_tools
    assert 'restart: "no"' in database_tools
    assert "postgres:18.6-bookworm" in restore_db
    assert "/var/lib/postgresql/data" in restore_db
    assert "database-recovery" in restore_db
    assert 'restart: "no"' in restore_db


def test_operations_monitor_is_separate_private_and_restartable():
    compose = VRT_COMPOSE.read_text(encoding="utf-8")
    monitor = compose.split("  operations-monitor:", maxsplit=1)[1].split(
        "  backup-worker:", maxsplit=1
    )[0]

    assert "monitoring" in monitor
    assert "scripts/monitor_operations.py" in monitor
    assert "http://api:8000/api/v1/readiness" in monitor
    assert "http://small-step-vllm:8000/health" in monitor
    assert ":/backups:ro" in monitor
    assert 'user: "0:0"' in monitor
    assert "operations_monitor_data:/app/data" in monitor
    assert "no-new-privileges:true" in monitor
    assert "docker.sock" not in monitor
    assert "DATABASE_URL" not in monitor
    assert "SUPABASE" not in monitor
    assert "SPEAKER_DIARIZATION_TOKEN" not in monitor
    assert "depends_on:" not in monitor
    assert "restart: unless-stopped" in monitor


def test_backup_worker_is_scheduled_hardened_and_uses_the_private_backup_mount():
    compose = VRT_COMPOSE.read_text(encoding="utf-8")
    backup_worker = compose.split("  backup-worker:", maxsplit=1)[1].split(
        "  database-tools:", maxsplit=1
    )[0]

    assert "backup" in backup_worker
    assert "Dockerfile.database-tools" in backup_worker
    assert "scripts/schedule_database_backups.py" in backup_worker
    assert "DATABASE_BACKUP_HOST_DIR" in backup_worker
    assert "no-new-privileges:true" in backup_worker
    assert "read_only: true" in backup_worker
    assert "restart: unless-stopped" in backup_worker
