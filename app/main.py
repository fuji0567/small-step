from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.config import Settings, get_settings
from app.database import create_database_engine, create_session_factory
from app.database_migrations import prepare_database


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
    application.include_router(router)
    application.mount(
        "/teacher",
        StaticFiles(directory=Path(__file__).parent / "web", html=True),
        name="teacher-web",
    )
    application.mount(
        "/guardian",
        StaticFiles(directory=Path(__file__).parent / "guardian", html=True),
        name="guardian-web",
    )
    return application


app = create_app()
