import json
from collections.abc import AsyncIterator

import httpx

from app.errors import AppError
from app.llm.base import Message, ProviderTimeout


class OllamaProvider:
    name = "ollama"

    def __init__(
        self,
        base_url: str,
        model: str,
        num_ctx: int,
        max_tokens: int,
        timeout_s: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url
        self.model = model
        self.num_ctx = num_ctx
        self.max_tokens = max_tokens
        self.timeout = httpx.Timeout(timeout_s, connect=5)
        self.transport = transport

    def unavailable(self) -> AppError:
        return AppError("provider_unavailable", f"Ollama is not reachable at {self.base_url}. Start it with `ollama serve`.")

    def model_missing(self) -> AppError:
        return AppError("provider_unavailable", f"The model {self.model} is not pulled. Run `ollama pull {self.model}`.")

    async def stream(self, system: str, messages: list[Message]) -> AsyncIterator[str]:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "stream": True,
            "think": False,
            "options": {"num_ctx": self.num_ctx, "num_predict": self.max_tokens},
        }
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout, transport=self.transport) as client:
                async with client.stream("POST", "/api/chat", json=body) as res:
                    if res.status_code == 404:
                        raise self.model_missing()
                    if res.status_code != 200:
                        detail = (await res.aread()).decode(errors="replace")[:200]
                        raise AppError("provider_unavailable", f"Ollama returned {res.status_code}: {detail}")
                    async for line in res.aiter_lines():
                        if not line:
                            continue
                        chunk = json.loads(line)
                        if "error" in chunk:
                            raise AppError("provider_unavailable", f"Ollama error: {chunk['error']}")
                        if text := chunk.get("message", {}).get("content"):
                            yield text
        except httpx.ConnectError as exc:
            raise self.unavailable() from exc
        except httpx.TimeoutException as exc:
            raise ProviderTimeout() from exc


async def ollama_status(base_url: str, model: str) -> tuple[bool, str | None]:
    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=2) as client:
            res = await client.get("/api/tags")
    except httpx.HTTPError:
        return False, f"Ollama is not reachable at {base_url}. Start it with `ollama serve`."
    names = {m["name"] for m in res.json().get("models", [])}
    if model not in names and f"{model}:latest" not in names:
        return False, f"The model {model} is not pulled. Run `ollama pull {model}`."
    return True, None
