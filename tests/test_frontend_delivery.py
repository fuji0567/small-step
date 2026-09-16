import os
import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.config import Settings


def development_settings(tmp_path: Path) -> Settings:
    return Settings(database_url=f"sqlite:///{tmp_path}/test.db", auth_mode="development")


def write_complete_frontend(directory: Path) -> None:
    (directory / "_app/immutable").mkdir(parents=True)
    (directory / "guardian").mkdir()
    (directory / "200.html").write_text(
        '<!doctype html><script type="module" src="/_app/immutable/app-123.js"></script>',
        encoding="utf-8",
    )
    (directory / "guardian/index.html").write_text(
        '<!doctype html><h1>配信アーカイブ</h1>', encoding="utf-8"
    )
    (directory / "_app/immutable/app-123.js").write_text("export {};", encoding="utf-8")


def write_complete_recorder(directory: Path) -> None:
    (directory / "assets").mkdir(parents=True)
    (directory / "index.html").write_text(
        '<!doctype html><script type="module" src="/rec/assets/app-123.js"></script>',
        encoding="utf-8",
    )
    (directory / "assets/app-123.js").write_text("export {};", encoding="utf-8")


def test_development_without_a_build_leaves_frontend_urls_unmounted(tmp_path, monkeypatch):
    monkeypatch.setattr(main_module, "FRONTEND_DIST", tmp_path / "missing-frontend-dist")
    application = main_module.create_app(development_settings(tmp_path))

    with TestClient(application) as client:
        assert client.get("/teacher/").status_code == 404
        assert client.get("/guardian/").status_code == 404
        assert client.get("/api/v1/health").json() == {"status": "ok"}


def test_partial_frontend_build_fails_clearly(tmp_path, monkeypatch):
    frontend_dist = tmp_path / "frontend-dist"
    frontend_dist.mkdir()
    (frontend_dist / "200.html").write_text("incomplete", encoding="utf-8")
    monkeypatch.setattr(main_module, "FRONTEND_DIST", frontend_dist)

    with pytest.raises(RuntimeError, match="frontend build is incomplete"):
        main_module.create_app(development_settings(tmp_path))


def test_production_requires_a_frontend_build(tmp_path):
    missing = tmp_path / "missing-frontend-dist"

    with pytest.raises(RuntimeError, match="frontend build is missing"):
        main_module._should_serve_frontend(missing, production=True)


def test_recorder_build_is_optional_when_disabled_and_required_when_enabled_in_production(tmp_path):
    missing = tmp_path / "missing-recorder-dist"
    assert main_module._should_serve_recorder(missing, enabled=False, production=False) is False
    with pytest.raises(RuntimeError, match="Recorder frontend build is missing"):
        main_module._should_serve_recorder(missing, enabled=True, production=True)

    incomplete = tmp_path / "stale-recorder-dist"
    incomplete.mkdir()
    assert main_module._should_serve_recorder(incomplete, enabled=False, production=True) is False


def test_recorder_delivery_redirect_cache_and_isolation(tmp_path, monkeypatch):
    frontend_dist = tmp_path / "frontend-dist"
    recorder_dist = tmp_path / "recorder-dist"
    write_complete_frontend(frontend_dist)
    write_complete_recorder(recorder_dist)
    monkeypatch.setattr(main_module, "FRONTEND_DIST", frontend_dist)
    monkeypatch.setattr(main_module, "RECORDER_DIST", recorder_dist)
    application = main_module.create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path}/recorder.db",
            auth_mode="development",
            recorder_enabled=True,
        )
    )

    with TestClient(application) as client:
        root = client.get("/rec", follow_redirects=False)
        index = client.get("/rec/")
        asset = client.get("/rec/assets/app-123.js")
        missing_asset = client.get("/rec/assets/missing.js")
        teacher = client.get("/teacher/")
        api = client.get("/api/v1/not-a-route")

    assert root.status_code == 307
    assert urlsplit(root.headers["location"]).path == "/rec/"
    assert root.headers["cache-control"] == "no-cache"
    assert index.status_code == 200
    assert index.headers["cache-control"] == "no-cache"
    assert asset.status_code == 200
    assert asset.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert missing_asset.status_code == 404
    assert teacher.status_code == 200
    assert teacher.headers["cache-control"] == "no-cache"
    assert api.status_code == 404


def test_svelte_frontends_use_teacher_only_spa_fallback(tmp_path, monkeypatch):
    frontend_dist = tmp_path / "frontend-dist"
    write_complete_frontend(frontend_dist)
    monkeypatch.setattr(main_module, "FRONTEND_DIST", frontend_dist)
    application = main_module.create_app(development_settings(tmp_path))

    with TestClient(application) as client:
        teacher_redirect = client.get("/teacher", follow_redirects=False)
        guardian_redirect = client.get("/guardian", follow_redirects=False)
        teacher = client.get("/teacher/")
        deep_teacher = client.get("/teacher/review/00000000-0000-0000-0000-000000000001/")
        unknown_teacher = client.get("/teacher/not-a-route")
        guardian = client.get("/guardian/")
        asset = client.get("/_app/immutable/app-123.js")
        missing_asset = client.get("/_app/immutable/missing.js")
        missing_api = client.get("/api/v1/not-a-route")
        missing_guardian = client.get("/guardian/not-a-route")
        missing_teacher_preview = client.get("/teacher-next/")
        missing_guardian_preview = client.get("/guardian-next/")
        missing_other = client.get("/not-a-route")

    assert teacher_redirect.status_code == 307
    assert urlsplit(teacher_redirect.headers["location"]).path == "/teacher/"
    assert teacher_redirect.headers["cache-control"] == "no-cache"
    assert guardian_redirect.status_code == 307
    assert urlsplit(guardian_redirect.headers["location"]).path == "/guardian/"
    assert guardian_redirect.headers["cache-control"] == "no-cache"
    assert teacher.status_code == 200
    assert teacher.headers["content-type"].startswith("text/html")
    assert teacher.headers["cache-control"] == "no-cache"
    assert deep_teacher.status_code == 200
    assert deep_teacher.headers["cache-control"] == "no-cache"
    assert unknown_teacher.status_code == 200
    assert unknown_teacher.headers["content-type"].startswith("text/html")
    assert guardian.status_code == 200
    assert guardian.headers["cache-control"] == "no-cache"
    assert asset.status_code == 200
    assert asset.headers["content-type"].startswith(("application/javascript", "text/javascript"))
    assert asset.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert missing_asset.status_code == 404
    assert missing_api.status_code == 404
    assert missing_api.headers["content-type"].startswith("application/json")
    assert missing_guardian.status_code == 404
    assert missing_teacher_preview.status_code == 404
    assert missing_guardian_preview.status_code == 404
    assert missing_other.status_code == 404


@pytest.mark.skipif(
    os.environ.get("SMALL_STEP_TEST_BUILT_FRONTEND") != "1",
    reason="set SMALL_STEP_TEST_BUILT_FRONTEND=1 after npm run build",
)
def test_built_frontend_assets_are_served_without_external_teacher_origins(tmp_path):
    frontend_dist = main_module.FRONTEND_DIST
    assert main_module._frontend_dist_is_complete(frontend_dist), (
        "Build the frontend before running delivery tests: cd frontend && npm run build"
    )
    application = main_module.create_app(development_settings(tmp_path))

    with TestClient(application) as client:
        teacher = client.get("/teacher/review/00000000-0000-0000-0000-000000000001/")
        guardian = client.get("/guardian/")
        asset_paths = set(re.findall(r'(?:src|href)="(/_app/[^"]+)"', teacher.text + guardian.text))
        assert asset_paths
        assets = {path: client.get(path) for path in asset_paths}

    assert teacher.status_code == 200
    assert guardian.status_code == 200
    assert "https://" not in teacher.text
    assert "http://" not in teacher.text
    for path, response in assets.items():
        assert response.status_code == 200, path
        assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
        assert response.headers["content-type"].startswith(
            ("application/javascript", "text/javascript", "text/css")
        )
