from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.api import health
from app.api.errors import register_error_handlers
from app.api.middleware import request_id_middleware
from app.config import get_settings
from app.db.pool import apply_schema, create_pool
from app.logging import configure_logging

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    app.state.pool = create_pool(settings.database_url)
    await app.state.pool.open(wait=False)
    try:
        await apply_schema(app.state.pool)
        log.info("schema_applied")
    except Exception as exc:
        log.error("db_error", error_code="db_unavailable", stage="schema", error=type(exc).__name__)
    yield
    await app.state.pool.close()


def create_app() -> FastAPI:
    app = FastAPI(title="Lenny Growth Assistant", lifespan=lifespan)
    app.middleware("http")(request_id_middleware)
    register_error_handlers(app)
    app.include_router(health.router, prefix="/api/v1")
    return app


app = create_app()
