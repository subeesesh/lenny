"""Day-1 spike (architecture §6.3): can claude-agent-sdk query() drive qwen3:4b via Ollama with an in-process tool?

Usage: python spike/agent_sdk_ollama.py
Runs against Ollama, then against Anthropic if ANTHROPIC_API_KEY is set.
"""

import asyncio
import os
import time

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    create_sdk_mcp_server,
    query,
    tool,
)

QUESTION = "What does Lenny's podcast say about finding product-market fit? Use the search_transcripts tool."
FIXED_RESULT = "[1] Rahul Vohra (Superhuman): measure PMF by asking users how disappointed they'd be without the product; aim for 40% 'very disappointed'."

calls: list[dict] = []


@tool("search_transcripts", "Search Lenny's Podcast transcripts for relevant passages.", {"query": str})
async def search_transcripts(args: dict) -> dict:
    calls.append(args)
    return {"content": [{"type": "text", "text": FIXED_RESULT}]}


async def run(label: str, model: str, env: dict[str, str]) -> None:
    calls.clear()
    server = create_sdk_mcp_server(name="lenny", version="0.1.0", tools=[search_transcripts])
    options = ClaudeAgentOptions(
        model=model,
        system_prompt="You answer questions about Lenny's Podcast. Always call search_transcripts first, then answer from its result.",
        mcp_servers={"lenny": server},
        tools=[],
        allowed_tools=["mcp__lenny__search_transcripts"],
        max_turns=4,
        setting_sources=[],
        env=env,
    )
    start = time.perf_counter()
    first_token: float | None = None
    answer, error = "", None
    try:
        async for msg in query(prompt=QUESTION, options=options):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if first_token is None:
                        first_token = time.perf_counter() - start
                    if isinstance(block, TextBlock):
                        answer += block.text
                    elif isinstance(block, ToolUseBlock):
                        print(f"  tool_use: {block.name} {block.input}")
            elif isinstance(msg, ResultMessage):
                if msg.is_error:
                    error = f"{msg.subtype}: {msg.result}"
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    total = time.perf_counter() - start
    print(f"== {label} ({model})")
    print(f"  ran: {error is None}  error: {error}")
    print(f"  tool called: {len(calls)}x {calls}")
    print(f"  latency: first block {first_token and round(first_token, 1)}s, total {total:.1f}s")
    print(f"  answer: {answer.strip()[:400]!r}")


async def main() -> None:
    await run(
        "ollama",
        "qwen3:4b",
        {"ANTHROPIC_BASE_URL": "http://localhost:11434", "ANTHROPIC_AUTH_TOKEN": "ollama", "ANTHROPIC_API_KEY": ""},
    )
    if os.environ.get("ANTHROPIC_API_KEY"):
        await run("anthropic", os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"), {})
    else:
        print("== anthropic: skipped (ANTHROPIC_API_KEY not set)")


if __name__ == "__main__":
    asyncio.run(main())
