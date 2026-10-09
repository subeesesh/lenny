from collections.abc import AsyncIterator
from typing import Protocol

import structlog

from app.errors import AppError

log = structlog.get_logger()

Message = dict[str, str]


class Provider(Protocol):
    name: str
    model: str

    def stream(self, system: str, messages: list[Message]) -> AsyncIterator[str]: ...


class ProviderTimeout(AppError):
    def __init__(self, message: str = "The model took too long to respond.") -> None:
        super().__init__("provider_timeout", message)


async def stream_with_retry(provider: Provider, system: str, messages: list[Message]) -> AsyncIterator[str]:
    """Retry once on timeout, but only if nothing was streamed yet (a retry mid-answer would duplicate text)."""
    for attempt in (1, 2):
        started = False
        try:
            async for token in provider.stream(system, messages):
                started = True
                yield token
            return
        except ProviderTimeout:
            log.warning("provider_timeout", provider=provider.name, model=provider.model, attempt=attempt)
            if started or attempt == 2:
                raise
