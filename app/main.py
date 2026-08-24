from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.config import Settings, get_settings
from app.database import create_database_engine, create_session_factory, initialise_database


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or get_settings()
    engine = create_database_engine(runtime_settings.database_url)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        initialise_database(engine)
        yield
        engine.dispose()

    application = FastAPI(
        title="Otayori AI Backend",
        version="0.1.0",
        description=(
            "Privacy-filtered kindergarten growth and incident record API. "
            "Raw audio must remain inside the kindergarten edge environment."
        ),
        lifespan=lifespan,
    )
    application.state.settings = runtime_settings
    application.state.engine = engine
    application.state.session_factory = create_session_factory(engine)
    application.include_router(router)
    return application


app = create_app()
