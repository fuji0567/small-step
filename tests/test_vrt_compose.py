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
