from dataclasses import dataclass

from app.config import Settings
from app.llm.anthropic import NO_KEY_MESSAGE, AnthropicProvider, OllamaSdkProvider
from app.llm.base import Provider
from app.llm.ollama import OllamaProvider, ollama_status


@dataclass
class Active:
    provider: str
    model: str


def default_model(settings: Settings, provider: str) -> str:
    return settings.anthropic_model if provider == "anthropic" else settings.ollama_model


def make_provider(settings: Settings, active: Active) -> Provider:
    if active.provider == "anthropic":
        return AnthropicProvider(settings.anthropic_api_key.get_secret_value(), active.model, settings.llm_timeout_s)
    if active.provider == "ollama-sdk":
        return OllamaSdkProvider(settings.ollama_base_url, active.model, settings.llm_timeout_s)
    return OllamaProvider(
        settings.ollama_base_url, active.model, settings.ollama_num_ctx, settings.llm_max_tokens, settings.llm_timeout_s,
        settings.ollama_num_gpu,
    )


async def provider_statuses(settings: Settings) -> list[dict[str, object]]:
    ollama_ok, ollama_reason = await ollama_status(settings.ollama_base_url, settings.ollama_model)
    has_key = bool(settings.anthropic_api_key.get_secret_value())
    return [
        {"name": "ollama", "label": "Local", "model": settings.ollama_model, "available": ollama_ok, "reason": ollama_reason},
        {
            "name": "ollama-sdk",
            "label": "Local · Agent SDK",
            "model": settings.ollama_model,
            "available": ollama_ok,
            "reason": ollama_reason,
        },
        {
            "name": "anthropic",
            "label": "Cloud",
            "model": settings.anthropic_model,
            "available": has_key,
            "reason": None if has_key else NO_KEY_MESSAGE,
        },
    ]
