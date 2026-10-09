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
    previous_user,
    say,
    start_generation,
    topic_of,
)
from app.agent.essay import clean_output, title_of
from app.llm.base import Message
from app.security.sanitize import ArtifactRejected, check_size, sanitize_html

H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)
TAG = re.compile(r"<[^>]+>")

log = structlog.get_logger()


def artifact_type(content: str) -> str:
    if re.search(r"\bmarkdown\b", content, re.I):
        return "markdown"
    if re.search(r"\bhtml\b|\bone-pager\b", content, re.I):
        return "html"
    return "markdown"


def html_title(html: str, fallback: str) -> str:
    match = H1.search(html)
    return (TAG.sub("", match.group(1)) if match else fallback).strip()[:120]


def finish(kind: str, raw: str, fallback_title: str) -> Draft:
    text = clean_output(raw)
    if kind == "html":
        clean = sanitize_html(text)
        return Draft("html", html_title(clean, fallback_title), clean)
    check_size(text)
    return Draft("markdown", title_of(text, fallback_title), text)


async def run_artifact(
    content: str,
    history: list[Message],
    retriever: Retriever,
    provider_factory: ProviderFactory,
    skills: dict[str, str],
    result: TurnResult,
) -> AsyncIterator[Event]:
    yield "status", {"stage": "retrieving"}
    retrieval = await retriever(topic_of(content), previous_user(history))
    if retrieval.refusal:
        async for event in say(result, retrieval.refusal):
            yield event
        return
    provider = provider_factory()
    for event in start_generation(provider, retrieval.hits, result):
        yield event
    kind = artifact_type(content)
    request = f"{context_block(retrieval.hits)}\n\nFormat: {kind.upper()}. Request: {content}"
    raw = await generate(provider, skills["artifact"], [{"role": "user", "content": request}])
    try:
        result.artifact = finish(kind, raw, content)
    except ArtifactRejected as exc:
        log.warning("artifact_rejected", reason=str(exc))
        result.text = f"I couldn't save that document. {exc}"
        yield "token", {"text": result.text}
        return
    label = "one-pager" if kind == "html" else "document"
    result.text = f"Here's your {label}: **{result.artifact.title}**. It's open in the viewer."
    yield "token", {"text": result.text}
