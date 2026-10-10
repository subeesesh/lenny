from typing import Any, Literal

import structlog
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.config import get_settings
from app.errors import AppError
from app.llm.anthropic import NO_KEY_MESSAGE
from app.llm.providers import Active, default_model, provider_statuses

router = APIRouter()
log = structlog.get_logger()


class ConfigUpdate(BaseModel):
    provider: Literal["ollama", "ollama-sdk", "anthropic"]
    model: str | None = Field(None, min_length=1, max_length=100)


@router.get("/config")
async def get_config(request: Request) -> dict[str, Any]:
    active: Active = request.app.state.active
    return {
        "active": {"provider": active.provider, "model": active.model},
        "providers": await provider_statuses(get_settings()),
    }


@router.put("/config")
async def put_config(body: ConfigUpdate, request: Request) -> dict[str, Any]:
    settings = get_settings()
    if body.provider == "anthropic" and not settings.anthropic_api_key.get_secret_value():
        raise AppError("provider_not_configured", NO_KEY_MESSAGE)
    request.app.state.active = Active(body.provider, body.model or default_model(settings, body.provider))
    log.info("provider_set", provider=body.provider, model=request.app.state.active.model)
    return await get_config(request)
