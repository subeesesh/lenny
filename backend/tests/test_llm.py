import json
from collections.abc import Callable

import httpx
import pytest
from pydantic import SecretStr

from app.config import Settings
from app.errors import AppError
from app.llm.anthropic import AnthropicProvider, OllamaSdkProvider, render_prompt
from app.llm.base import Provider, ProviderTimeout, stream_with_retry
from app.llm.ollama import OllamaProvider
from app.llm.providers import Active, default_model, make_provider
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
    assert seen["keep_alive"] == "30m"
    assert seen["options"] == {"num_ctx": 8192, "num_predict": 3000}
    assert seen["messages"][0] == {"role": "system", "content": "sys"}


def test_ollama_num_gpu_sent_only_when_set() -> None:
    assert "num_gpu" not in ollama(lambda r: httpx.Response(200)).options()
    provider = OllamaProvider("http://ollama", "m", 8192, 3000, 5, num_gpu=16)
    assert provider.options()["num_gpu"] == 16


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


def test_ollama_sdk_provider_points_the_agent_sdk_at_ollama() -> None:
    provider = OllamaSdkProvider("http://host.docker.internal:11434", "qwen3:4b-instruct-2507-q4_K_M", 120)
    options = provider.options("system prompt")
    assert provider.name == "ollama-sdk"
    assert options.env["ANTHROPIC_BASE_URL"] == "http://host.docker.internal:11434"
    assert options.env["ANTHROPIC_API_KEY"] == ""
    assert options.env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] == "1"
    assert options.model == "qwen3:4b-instruct-2507-q4_K_M" and options.tools == [] and options.max_turns == 1


def test_make_provider_routes_each_name() -> None:
    settings = Settings(anthropic_api_key=SecretStr("sk-test"))
    assert isinstance(make_provider(settings, Active("ollama", "m")), OllamaProvider)
    assert isinstance(make_provider(settings, Active("ollama-sdk", "m")), OllamaSdkProvider)
    assert isinstance(make_provider(settings, Active("anthropic", "c")), AnthropicProvider)


async def test_ollama_sdk_names_the_fix_before_starting_the_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    async def missing(base_url: str, model: str, fix: str | None = None) -> tuple[bool, str | None]:
        return False, fix

    def no_cli(**kwargs: object) -> None:
        raise AssertionError("the CLI must not start when Ollama is not ready")

    monkeypatch.setattr("app.llm.anthropic.ollama_status", missing)
    monkeypatch.setattr("app.llm.anthropic.query", no_cli)
    provider = OllamaSdkProvider("http://ollama", "lenny-qwen3-4b", 120)
    with pytest.raises(AppError) as err:
        await collect(provider)
    assert err.value.code == "provider_unavailable"
    assert "ollama create lenny-qwen3-4b -f ollama/Modelfile" in err.value.message


def test_default_model_per_provider() -> None:
    settings = Settings()
    assert default_model(settings, "ollama-sdk") == settings.ollama_sdk_model == "lenny-qwen3-4b"
    assert default_model(settings, "ollama") == settings.ollama_model
    assert default_model(settings, "anthropic") == settings.anthropic_model
