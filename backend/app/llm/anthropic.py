import asyncio
from collections.abc import AsyncIterator

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKError, ResultMessage, StreamEvent, query

from app.errors import AppError
from app.llm.base import Message, ProviderTimeout

NO_KEY_MESSAGE = "Cloud is not configured. Add ANTHROPIC_API_KEY to .env and restart."


def render_prompt(messages: list[Message]) -> str:
    *history, last = messages
    if not history:
        return last["content"]
    turns = "\n\n".join(f"{m['role'].capitalize()}: {m['content']}" for m in history)
    return f"Earlier in this conversation:\n{turns}\n\n{last['content']}"


class AnthropicProvider:
    """Claude via the Claude Agent SDK, with every built-in tool disabled (architecture §6.3)."""

    name = "anthropic"

    def __init__(self, api_key: str, model: str, timeout_s: float) -> None:
        if not api_key:
            raise AppError("provider_not_configured", NO_KEY_MESSAGE)
        self.api_key = api_key
        self.model = model
        self.timeout_s = timeout_s

    def options(self, system: str) -> ClaudeAgentOptions:
        return ClaudeAgentOptions(
            model=self.model,
            system_prompt=system,
            tools=[],
            allowed_tools=[],
            max_turns=1,
            setting_sources=[],
            include_partial_messages=True,
            env={"ANTHROPIC_API_KEY": self.api_key},
        )

    async def stream(self, system: str, messages: list[Message]) -> AsyncIterator[str]:
        events = query(prompt=render_prompt(messages), options=self.options(system)).__aiter__()
        while True:
            try:
                msg = await asyncio.wait_for(events.__anext__(), self.timeout_s)
            except StopAsyncIteration:
                return
            except TimeoutError as exc:
                raise ProviderTimeout() from exc
            except ClaudeSDKError as exc:
                raise AppError("provider_unavailable", f"Anthropic request failed: {exc}") from exc
            if isinstance(msg, StreamEvent):
                delta = msg.event.get("delta", {})
                if msg.event.get("type") == "content_block_delta" and delta.get("type") == "text_delta":
                    yield delta["text"]
            elif isinstance(msg, ResultMessage) and msg.is_error:
                raise AppError("provider_unavailable", f"Anthropic request failed: {msg.result or msg.subtype}")
