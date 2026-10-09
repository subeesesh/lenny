import httpx
import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.db.pool import count_chunks

router = APIRouter()
log = structlog.get_logger()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


async def ollama_reachable(base_url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            return (await client.get(f"{base_url}/api/tags")).status_code == 200
    except httpx.HTTPError:
        return False


@router.get("/ready")
async def ready(request: Request) -> JSONResponse:
    settings = get_settings()
    try:
        chunks: int | None = await count_chunks(request.app.state.pool)
        db = True
    except Exception as exc:
        log.warning("db_error", error_code="db_unavailable", error=type(exc).__name__)
        chunks, db = None, False
    body = {
        "db": db,
        "ollama": await ollama_reachable(settings.ollama_base_url),
        "anthropic_key": bool(settings.anthropic_api_key.get_secret_value()),
        "chunks": chunks,
    }
    return JSONResponse(body, status_code=200 if db else 503)
