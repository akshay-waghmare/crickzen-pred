"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlmodel import Session

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)


def create_app(
    settings_override: Settings | None = None,
    engine_override=None,
) -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = settings_override or get_settings()

    import app.config as config_module
    config_module._settings = settings

    from app.database import (
        create_db_and_tables,
        init_engine,
        periodic_token_purge,
        purge_expired_tokens,
        seed_admin_user,
    )

    if engine_override is not None:
        import app.database as db_module
        db_module._engine = engine_override
        engine = engine_override
    else:
        engine = init_engine(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup
        create_db_and_tables(engine)
        with Session(engine) as session:
            seed_admin_user(session, settings)
            purge_expired_tokens(session)

        purge_task = asyncio.create_task(periodic_token_purge())
        auto_task: asyncio.Task | None = None
        auto_scheduler = None
        if settings.AUTO_PREDICTIONS_ENABLED:
            from app.auto_scheduler import AutoPredictionScheduler
            from app.prediction_manager import PredictionManager

            auto_scheduler = AutoPredictionScheduler(PredictionManager.get_instance(), settings)
            app.state.auto_scheduler = auto_scheduler
            auto_task = asyncio.create_task(auto_scheduler.run_forever())
        else:
            app.state.auto_scheduler = None
        logger.info("CrickenZen Dashboard started — %s", settings.DOMAIN)
        yield

        # Shutdown
        if auto_scheduler is not None:
            auto_scheduler.stop()
        if auto_task is not None:
            auto_task.cancel()
            try:
                await auto_task
            except asyncio.CancelledError:
                pass

        purge_task.cancel()
        try:
            await purge_task
        except asyncio.CancelledError:
            pass

        # Cleanup all running predictions
        from app.prediction_manager import PredictionManager
        PredictionManager.get_instance().cleanup_all()

    application = FastAPI(
        title="CrickenZen Dashboard",
        version=settings.APP_VERSION,
        lifespan=lifespan,
    )

    # Rate limiter
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # CORS
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Static files
    static_dir = Path(__file__).resolve().parent.parent / "static"
    if static_dir.exists():
        application.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Register routers
    from app.routers.auth import router as auth_router
    from app.routers.admin import router as admin_router
    from app.routers.live import router as live_router
    from app.routers.pages import router as pages_router
    from app.health import router as health_router

    application.include_router(auth_router)
    application.include_router(admin_router)
    application.include_router(live_router)
    application.include_router(health_router)
    # Pages router last (catch-all "/" route)
    application.include_router(pages_router)

    return application


# Module-level app instance for uvicorn
app = create_app()
