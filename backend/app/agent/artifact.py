import html
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
    sources_list,
    start_generation,
    timestamp_url,
    topic_of,
)
from app.agent.essay import clean_output, title_of
from app.llm.base import Message
from app.retrieval.search import Hit
from app.security.sanitize import ArtifactRejected, check_size, sanitize_html

H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)
MD_HEADING = re.compile(r"^(#{1,6})\s+(.+)$")
MD_BOLD = re.compile(r"\*\*(.+?)\*\*")
TAG = re.compile(r"<[^>]+>")
STYLE_ATTR = re.compile(r"\s+style\s*=\s*(\"[^\"]*\"|'[^']*')", re.I)
WRAPPER_TAG = re.compile(r"</?(?:section|div|header|footer)\b[^>]*>", re.I)
H2_START = re.compile(r"(?=<h2[\s>])", re.I)

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


def markdown_leftovers_to_html(text: str) -> str:
    """The 4B model sometimes slips into Markdown inside an HTML document; convert those blocks, keep real HTML."""
    out: list[str] = []
    for block in re.split(r"\n\s*\n", text.strip()):
        block = block.strip()
        if block.startswith("<"):
            out.append(block)
            continue
        paragraph: list[str] = []
        for line in block.splitlines():
            heading = MD_HEADING.match(line.strip())
            if heading:
                if paragraph:
                    out.append(f"<p>{' '.join(paragraph)}</p>")
                    paragraph = []
                level = len(heading.group(1))
                out.append(f"<h{level}>{MD_BOLD.sub(r'<strong>\1</strong>', heading.group(2).strip())}</h{level}>")
            elif line.strip():
                paragraph.append(MD_BOLD.sub(r"<strong>\1</strong>", line.strip()))
        if paragraph:
            out.append(f"<p>{' '.join(paragraph)}</p>")
    return "\n".join(out)


def structure_one_pager(fragment: str) -> str:
    """The viewer styles a fixed layout (header, one section per <h2>), so model styling and wrappers are dropped."""
    fragment = WRAPPER_TAG.sub("", STYLE_ATTR.sub("", fragment))
    head, *parts = H2_START.split(fragment)
    sections = "".join(f"<section>{part.strip()}</section>" for part in parts if part.strip())
    return f"<header>{head.strip()}</header>{sections}"


def sources_html(hits: list[Hit]) -> str:
    items = []
    for h in hits:
        label = html.escape(f"{h.guest or 'Unknown guest'} — {h.title}" + (f" ({h.ts})" if h.ts else ""))
        url = timestamp_url(h.url, h.ts)
        items.append(f'<li><a href="{html.escape(url)}">{label}</a></li>' if url else f"<li>{label}</li>")
    return f"<footer><h2>Sources</h2><ol>{''.join(items)}</ol></footer>"


def finish(kind: str, raw: str, fallback_title: str, hits: list[Hit]) -> Draft:
    text = clean_output(raw)
    if kind == "html":
        body = structure_one_pager(markdown_leftovers_to_html(text)) + sources_html(hits)
        clean = sanitize_html(body)
        return Draft("html", html_title(clean, fallback_title), clean)
    text = f"{text}\n\n{sources_list(hits)}\n"
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
        result.artifact = finish(kind, raw, content, retrieval.hits)
    except ArtifactRejected as exc:
        log.warning("artifact_rejected", reason=str(exc))
        result.text = f"I couldn't save that document. {exc}"
        yield "token", {"text": result.text}
        return
    label = "one-pager" if kind == "html" else "document"
    result.text = f"Here's your {label}: **{result.artifact.title}**. It's open in the viewer."
    yield "token", {"text": result.text}
