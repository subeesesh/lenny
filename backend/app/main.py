from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.agent.skills import load_skills
from app.api import config, health, sessions
from app.api.errors import register_error_handlers
from app.api.middleware import request_id_middleware
from app.config import get_settings
from app.db.pool import apply_schema, create_pool
from app.llm.providers import Active, default_model, make_provider
from app.logging import configure_logging
from app.retrieval.search import Retrieval, ollama_query_embedder, retrieve

log = structlog.get_logger()


def create_app(database_url: str | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings = get_settings()
        configure_logging(settings.log_level)
        pool = app.state.pool = create_pool(database_url or settings.database_url)
        await pool.open(wait=False)
        try:
            await apply_schema(pool)
            log.info("schema_applied")
        except Exception as exc:
            log.error("db_error", error_code="db_unavailable", stage="schema", error=type(exc).__name__)
        embed = ollama_query_embedder(settings.ollama_base_url, settings.embed_model)

        async def retriever(question: str, previous: str | None) -> Retrieval:
            return await retrieve(
                pool, embed, question, previous, settings.retrieval_top_k, settings.retrieval_min_score
            )

        app.state.skills = load_skills()
        app.state.active = Active(settings.llm_provider, default_model(settings, settings.llm_provider))
        app.state.retriever = retriever
        app.state.provider_factory = lambda: make_provider(settings, app.state.active)
        yield
        await pool.close()

    app = FastAPI(title="Lenny Growth Assistant", lifespan=lifespan)
    app.middleware("http")(request_id_middleware)
    register_error_handlers(app)
    for module in (health, config, sessions):
        app.include_router(module.router, prefix="/api/v1")
    return app


app = create_app()
