import re
from collections.abc import AsyncIterator

import structlog

from app.agent.context import (
    Draft,
    Event,
    ProviderFactory,
    Retriever,
    TurnResult,
    context_block,
    generate,
    previous_answer,
    previous_user,
    say,
    sources_list,
    start_generation,
    topic_of,
)
from app.llm.base import Message, Provider

MIN_WORDS, TARGET_WORDS, MAX_WORDS = 1125, 1250, 1375
ESSAY_TOP_K = 10
WORD = re.compile(r"[A-Za-z0-9][\w'’-]*")
TITLE = re.compile(r"^#\s+(.+)$", re.M)
FENCE = re.compile(r"^```\w*\n|\n```\s*$")

log = structlog.get_logger()


def word_count(markdown: str) -> int:
    return len(WORD.findall(markdown))


def clean_output(text: str) -> str:
    return FENCE.sub("", text.strip()).strip()


def title_of(markdown: str, fallback: str) -> str:
    match = TITLE.search(markdown)
    return (match.group(1) if match else fallback).strip()[:120]


def essay_request(content: str, history: list[Message], context: str) -> str:
    earlier = previous_answer(history)
    extra = f"\n\nThe previous answer in this chat, for the topic:\n{earlier[:2000]}" if earlier else ""
    return f"{context}{extra}\n\nWrite the essay. Request: {content}"


def length_fix(words: int) -> str:
    """Asking for a word delta, not a new total, keeps the 4B model's rewrite inside the range."""
    if words < MIN_WORDS:
        change = f"Add about {TARGET_WORDS - words} words by expanding the existing sections with more detail from the passages; do not add new sections."
    else:
        change = f"Cut about {words - TARGET_WORDS} words by tightening the existing sections; keep every section."
    return (
        f"The essay has {words} words and must end up between {MIN_WORDS:,} and {MAX_WORDS:,} words. {change} "
        "Keep the same idea, hook, takeaway and citations. Return the full essay, nothing else."
    )


async def write_essay(provider: Provider, system: str, messages: list[Message]) -> tuple[str, int, bool]:
    essay = clean_output(await generate(provider, system, messages))
    words = word_count(essay)
    if MIN_WORDS <= words <= MAX_WORDS:
        return essay, words, False
    log.info("essay_retry", first_word_count=words)
    retry = [*messages, {"role": "assistant", "content": essay}, {"role": "user", "content": length_fix(words)}]
    essay = clean_output(await generate(provider, system, retry))
    return essay, word_count(essay), True


async def run_essay(
    content: str,
    history: list[Message],
    retriever: Retriever,
    provider_factory: ProviderFactory,
    skills: dict[str, str],
    result: TurnResult,
) -> AsyncIterator[Event]:
    yield "status", {"stage": "retrieving"}
    retrieval = await retriever(topic_of(content), previous_user(history), ESSAY_TOP_K)
    if retrieval.refusal:
        async for event in say(result, retrieval.refusal):
            yield event
        return
    provider = provider_factory()
    for event in start_generation(provider, retrieval.hits, result):
        yield event
    request = essay_request(content, history, context_block(retrieval.hits))
    essay, words, retried = await write_essay(provider, skills["ship30"], [{"role": "user", "content": request}])
    log.info("essay_generated", word_count=words, retried=retried, in_range=MIN_WORDS <= words <= MAX_WORDS)
    title = title_of(essay, content)
    result.artifact = Draft("markdown", title, f"{essay}\n\n{sources_list(retrieval.hits)}\n")
    async for event in say_essay(result, title, words):
        yield event


async def say_essay(result: TurnResult, title: str, words: int) -> AsyncIterator[Event]:
    result.text = f"Here's your Ship 30 essay: **{title}** ({words:,} words). It's open in the viewer."
    yield "token", {"text": result.text}
