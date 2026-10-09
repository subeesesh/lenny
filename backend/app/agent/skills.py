from collections.abc import AsyncIterator
from pathlib import Path

import structlog

from app.agent.artifact import run_artifact
from app.agent.context import (
    Event,
    ProviderFactory,
    Retriever,
    TurnResult,
    context_block,
    previous_user,
    say,
    start_generation,
)
from app.agent.essay import run_essay
from app.agent.router import route
from app.llm.base import Message, stream_with_retry
from app.retrieval.search import Hit, Retrieval

SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills"
HISTORY_CHARS = 1000
CHAT_REPLY = (
    "Hi! I answer questions about Lenny's Podcast using only the episode transcripts, "
    "with numbered sources you can click. I can also write a Ship 30 style essay or "
    "make a one-pager from what the guests said. Try "
    "\"How do the guests think about finding product-market fit?\""
)

log = structlog.get_logger()


def load_skills() -> dict[str, str]:
    return {path.parent.name: path.read_text(encoding="utf-8") for path in SKILLS_DIR.glob("*/SKILL.md")}


def qa_messages(history: list[Message], hits: list[Hit], question: str) -> list[Message]:
    past = [{"role": m["role"], "content": m["content"][:HISTORY_CHARS]} for m in history]
    return [*past, {"role": "user", "content": f"{context_block(hits)}\n\nQuestion: {question}"}]


async def run_chat(result: TurnResult) -> AsyncIterator[Event]:
    yield "status", {"stage": "generating"}
    async for event in say(result, CHAT_REPLY):
        yield event


async def run_qa(
    content: str,
    history: list[Message],
    retriever: Retriever,
    provider_factory: ProviderFactory,
    skills: dict[str, str],
    result: TurnResult,
) -> AsyncIterator[Event]:
    yield "status", {"stage": "retrieving"}
    retrieval = await retriever(content, previous_user(history))
    if retrieval.refusal:
        async for event in say(result, retrieval.refusal):
            yield event
        return
    provider = provider_factory()
    for event in start_generation(provider, retrieval.hits, result):
        yield event
    async for token in stream_with_retry(provider, skills["qa"], qa_messages(history, retrieval.hits, content)):
        result.text += token
        yield "token", {"text": token}


async def run_turn(
    content: str,
    hint: str | None,
    history: list[Message],
    retriever: Retriever,
    provider_factory: ProviderFactory,
    skills: dict[str, str],
    result: TurnResult,
) -> AsyncIterator[Event]:
    result.route = route(content, hint)
    log.info("routed", route=result.route)

    async def recording_retriever(question: str, previous: str | None) -> Retrieval:
        retrieval = await retriever(question, previous)
        result.top_score = retrieval.top_score
        return retrieval

    if result.route == "chat":
        turn = run_chat(result)
    else:
        skill = {"essay": run_essay, "artifact": run_artifact}.get(result.route, run_qa)
        turn = skill(content, history, recording_retriever, provider_factory, skills, result)
    async for event in turn:
        yield event
