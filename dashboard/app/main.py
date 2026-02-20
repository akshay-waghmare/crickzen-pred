"""FastAPI application factory."""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlmodel import Session

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Rate limiter (shared across routers)
limiter = Limiter(key_func=get_remote_address)

# Jinja2 templates — resolved relative to dashboard/ directory
_template_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_template_dir))


def create_app(
    settings_override: Settings | None = None,
    engine_override=None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        settings_override: Override settings (used in tests).
        engine_override: Override database engine (used in tests).
    """
    settings = settings_override or get_settings()

    # Store settings for dependency injection
    import app.config as config_module

    config_module._settings = settings

    # Initialize database engine
    from app.database import create_db_and_tables, init_engine, periodic_token_purge, purge_expired_tokens, seed_admin_user

    if engine_override is not None:
        import app.database as db_module

        db_module._engine = engine_override
        engine = engine_override
    else:
        engine = init_engine(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Startup / shutdown lifecycle."""
        # Startup
        create_db_and_tables(engine)
        with Session(engine) as session:
            seed_admin_user(session, settings)
            purge_expired_tokens(session)

        # Start background token purge task
        purge_task = asyncio.create_task(periodic_token_purge())

        logger.info("Dashboard started — %s", settings.DOMAIN)
        yield

        # Shutdown
        purge_task.cancel()
        try:
            await purge_task
        except asyncio.CancelledError:
            pass

    app = FastAPI(
        title="CrickenZen Dashboard",
        version=settings.APP_VERSION,
        lifespan=lifespan,
    )

    # Rate limiter middleware
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Static files
    static_dir = Path(__file__).resolve().parent.parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Register routers
    from app.routers.auth import router as auth_router
    from app.routers.live import router as live_router
    from app.routers.pages import router as pages_router
    from app.health import router as health_router

    app.include_router(auth_router)
    app.include_router(live_router)
    app.include_router(health_router)
    # Pages router last (catch-all "/" route)
    app.include_router(pages_router)

    return app


# Module-level app instance for uvicorn
app = create_app()
