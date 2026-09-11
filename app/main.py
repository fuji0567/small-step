from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.config import Settings, get_settings
from app.database import create_database_engine, create_session_factory
from app.database_migrations import prepare_database

FRONTEND_DIST = Path(__file__).parent / "frontend_dist"
FRONTEND_REQUIRED_PATHS = (
    Path("200.html"),
    Path("_app"),
    Path("guardian/index.html"),
)


def _frontend_dist_is_complete(directory: Path) -> bool:
    return all((directory / path).exists() for path in FRONTEND_REQUIRED_PATHS) and any(
        path.is_file() for path in (directory / "_app").rglob("*")
    )


def _should_serve_frontend(directory: Path, *, production: bool) -> bool:
    if not directory.exists():
        if production:
            raise RuntimeError(
                "Svelte frontend build is missing. Run `npm ci && npm run build` in frontend/."
            )
        return False
    if not _frontend_dist_is_complete(directory):
        missing = [str(path) for path in FRONTEND_REQUIRED_PATHS if not (directory / path).exists()]
        if not any(path.is_file() for path in (directory / "_app").rglob("*")):
            missing.append("_app/<built asset>")
        raise RuntimeError(f"Svelte frontend build is incomplete: {', '.join(missing)}")
    return True


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or get_settings()
    engine = create_database_engine(runtime_settings.database_url)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        # SQLite remains the zero-setup local-development option. Applying the
        # checked-in migrations here also keeps local prototypes current.
        if engine.dialect.name == "sqlite":
            prepare_database(runtime_settings.database_url)
        yield
        engine.dispose()

    application = FastAPI(
        title="Otayori AI Backend",
        version="0.1.0",
        description=(
            "Privacy-filtered kindergarten growth and incident record API. "
            "Raw-audio uploads are disabled by default and are short-lived when cloud GPU mode is enabled."
        ),
        lifespan=lifespan,
    )
    application.state.settings = runtime_settings
    application.state.engine = engine
    application.state.session_factory = create_session_factory(engine)

    @application.middleware("http")
    async def frontend_cache_headers(request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/_app/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif path == "/teacher" or path.startswith("/teacher/"):
            response.headers["Cache-Control"] = "no-cache"
        elif path == "/guardian" or path.startswith("/guardian/"):
            response.headers["Cache-Control"] = "no-cache"
        return response

    application.include_router(router)

    if _should_serve_frontend(FRONTEND_DIST, production=runtime_settings.app_env == "production"):
        application.mount(
            "/_app",
            StaticFiles(directory=FRONTEND_DIST / "_app"),
            name="svelte-assets",
        )
        application.mount(
            "/guardian",
            StaticFiles(directory=FRONTEND_DIST / "guardian", html=True),
            name="guardian-web",
        )

        @application.get("/teacher", include_in_schema=False)
        def redirect_teacher_app() -> RedirectResponse:
            return RedirectResponse(url="/teacher/")

        @application.get("/teacher/{path:path}", include_in_schema=False)
        def serve_teacher_app() -> FileResponse:
            return FileResponse(FRONTEND_DIST / "200.html", media_type="text/html")

    return application


app = create_app()
