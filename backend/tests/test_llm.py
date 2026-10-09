import json
from collections.abc import Callable

import httpx
import pytest

from app.errors import AppError
from app.llm.anthropic import AnthropicProvider, render_prompt
from app.llm.base import Provider, ProviderTimeout, stream_with_retry
from app.llm.ollama import OllamaProvider
from tests.fakes import FakeProvider, timeout

MESSAGES = [{"role": "user", "content": "hi"}]


def ollama(handler: Callable[[httpx.Request], httpx.Response]) -> OllamaProvider:
    return OllamaProvider("http://ollama", "qwen3:4b", 8192, 3000, 5, transport=httpx.MockTransport(handler))


async def collect(provider: Provider, system: str = "sys") -> list[str]:
    return [t async for t in stream_with_retry(provider, system, MESSAGES)]


async def test_ollama_streams_with_thinking_off_and_num_ctx() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        lines = [{"message": {"content": "Hel"}}, {"message": {"content": "lo"}}, {"done": True}]
        return httpx.Response(200, text="\n".join(json.dumps(line) for line in lines))

    assert await collect(ollama(handler)) == ["Hel", "lo"]
    assert seen["think"] is False
    assert seen["options"] == {"num_ctx": 8192, "num_predict": 3000}
    assert seen["messages"][0] == {"role": "system", "content": "sys"}


async def test_ollama_down_is_provider_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(AppError) as err:
        await collect(ollama(handler))
    assert err.value.code == "provider_unavailable"
    assert "ollama serve" in err.value.message


async def test_ollama_model_missing_says_how_to_pull() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "model 'qwen3:4b' not found"})

    with pytest.raises(AppError) as err:
        await collect(ollama(handler))
    assert err.value.code == "provider_unavailable"
    assert "ollama pull qwen3:4b" in err.value.message


async def test_ollama_read_timeout_is_retried_once_then_provider_timeout() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("slow")

    with pytest.raises(ProviderTimeout):
        await collect(ollama(handler))
    assert calls == 2


async def test_timeout_retry_succeeds_on_second_attempt() -> None:
    provider = FakeProvider([timeout()], ["ok"])
    assert await collect(provider) == ["ok"]
    assert len(provider.calls) == 2


async def test_no_retry_after_tokens_were_streamed() -> None:
    provider = FakeProvider(["partial", timeout()], ["never"])
    with pytest.raises(ProviderTimeout):
        await collect(provider)
    assert len(provider.calls) == 1


def test_anthropic_without_key_is_not_configured() -> None:
    with pytest.raises(AppError) as err:
        AnthropicProvider("", "claude-sonnet-4-6", 120)
    assert err.value.code == "provider_not_configured"
    assert "ANTHROPIC_API_KEY" in err.value.message


def test_anthropic_prompt_includes_history() -> None:
    prompt = render_prompt([{"role": "user", "content": "q1"}, {"role": "assistant", "content": "a1"}, {"role": "user", "content": "q2"}])
    assert prompt == "Earlier in this conversation:\nUser: q1\n\nAssistant: a1\n\nq2"
