import asyncio
from collections.abc import AsyncIterator

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKError, ResultMessage, StreamEvent, query

from app.errors import AppError
from app.llm.base import Message, ProviderTimeout
from app.llm.ollama import create_fix, ollama_status

NO_KEY_MESSAGE = "Cloud is not configured. Add ANTHROPIC_API_KEY to .env and restart."


def render_prompt(messages: list[Message]) -> str:
    *history, last = messages
    if not history:
        return last["content"]
    turns = "\n\n".join(f"{m['role'].capitalize()}: {m['content']}" for m in history)
    return f"Earlier in this conversation:\n{turns}\n\n{last['content']}"


class AgentSdkProvider:
    """A model behind an Anthropic-compatible API, called through the Claude Agent SDK with every built-in tool disabled."""

    def __init__(self, name: str, label: str, model: str, timeout_s: float, env: dict[str, str]) -> None:
        self.name = name
        self.label = label
        self.model = model
        self.timeout_s = timeout_s
        self.env = env

    def options(self, system: str) -> ClaudeAgentOptions:
        return ClaudeAgentOptions(
            model=self.model,
            system_prompt=system,
            tools=[],
            allowed_tools=[],
            max_turns=1,
            setting_sources=[],
            include_partial_messages=True,
            env={**self.env, "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"},
        )

    def failed(self, detail: object) -> AppError:
        return AppError("provider_unavailable", f"{self.label} request failed: {detail}")

    async def check(self) -> None:
        """Hook for a fast reachability check before starting the CLI."""

    async def stream(self, system: str, messages: list[Message]) -> AsyncIterator[str]:
        await self.check()
        events = query(prompt=render_prompt(messages), options=self.options(system)).__aiter__()
        while True:
            try:
                msg = await asyncio.wait_for(events.__anext__(), self.timeout_s)
            except StopAsyncIteration:
                return
            except TimeoutError as exc:
                raise ProviderTimeout() from exc
            except ClaudeSDKError as exc:
                raise self.failed(exc) from exc
            if isinstance(msg, StreamEvent):
                delta = msg.event.get("delta", {})
                if msg.event.get("type") == "content_block_delta" and delta.get("type") == "text_delta":
                    yield delta["text"]
            elif isinstance(msg, ResultMessage) and msg.is_error:
                raise self.failed(msg.result or msg.subtype)


class AnthropicProvider(AgentSdkProvider):
    """Claude (architecture §6.3)."""

    def __init__(self, api_key: str, model: str, timeout_s: float) -> None:
        if not api_key:
            raise AppError("provider_not_configured", NO_KEY_MESSAGE)
        super().__init__("anthropic", "Anthropic", model, timeout_s, {"ANTHROPIC_API_KEY": api_key})


class OllamaSdkProvider(AgentSdkProvider):
    """The local Ollama model through the same SDK, via Ollama's Anthropic-compatible endpoint (architecture §6.3)."""

    def __init__(self, base_url: str, model: str, timeout_s: float) -> None:
        env = {"ANTHROPIC_BASE_URL": base_url, "ANTHROPIC_AUTH_TOKEN": "ollama", "ANTHROPIC_API_KEY": ""}
        super().__init__("ollama-sdk", "Ollama via the Agent SDK", model, timeout_s, env)
        self.base_url = base_url

    async def check(self) -> None:
        """Ollama down or the model missing would surface as a vague CLI error; name the fix instead."""
        ok, reason = await ollama_status(self.base_url, self.model, create_fix(self.model))
        if not ok:
            raise AppError("provider_unavailable", reason or "Ollama is not available.")
