import json
import math
import re
import zlib
from collections.abc import AsyncIterator
from typing import Any

from fastapi.testclient import TestClient

from app.errors import AppError
from app.llm.base import Message, ProviderTimeout
from app.retrieval.search import Hit, Retrieval

STOPWORDS = {"the", "is", "a", "an", "to", "of", "and", "what", "did", "on", "say", "about", "that", "in", "it"}


def bag_of_words(text: str) -> list[float]:
    vec = [0.0] * 768
    for word in re.findall(r"[a-z']+", text.lower()):
        if word not in STOPWORDS:
            vec[zlib.crc32(word.encode()) % 768] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


class RecordingEmbedder:
    def __init__(self) -> None:
        self.texts: list[str] = []

    async def __call__(self, text: str) -> list[float]:
        self.texts.append(text)
        return bag_of_words(text)


class FakeProvider:
    """Each attempt pops one script entry: a list of tokens, or an exception to raise (after the tokens before it)."""

    name = "fake"
    model = "fake-1"

    def __init__(self, *attempts: list[str | Exception]) -> None:
        self.attempts = list(attempts) or [["Hello ", "world [1]"]]
        self.calls: list[tuple[str, list[Message]]] = []

    async def stream(self, system: str, messages: list[Message]) -> AsyncIterator[str]:
        self.calls.append((system, messages))
        for item in self.attempts.pop(0) if len(self.attempts) > 1 else self.attempts[0]:
            if isinstance(item, Exception):
                raise item
            yield item


def timeout() -> ProviderTimeout:
    return ProviderTimeout()


def unavailable() -> AppError:
    return AppError("provider_unavailable", "Ollama is not reachable at http://x. Start it with `ollama serve`.")


HIT = Hit(1, "gamma", "Gamma episode", "Cy Guest", "https://www.youtube.com/watch?v=x", "00:01:05", "Cy Guest", "Retention compounds.", 0.81)


class FakeRetriever:
    def __init__(self, result: Retrieval | None = None) -> None:
        self.result = result or Retrieval(hits=[HIT], top_score=0.81)
        self.calls: list[tuple[str, str | None]] = []

    async def __call__(self, question: str, previous: str | None) -> Retrieval:
        self.calls.append((question, previous))
        return self.result


def use(client: TestClient, retriever: FakeRetriever | None = None, provider: FakeProvider | None = None) -> tuple[FakeRetriever, FakeProvider]:
    retriever, provider = retriever or FakeRetriever(), provider or FakeProvider()
    client.app.state.retriever = retriever
    client.app.state.provider_factory = lambda: provider
    return retriever, provider


def new_session(client: TestClient) -> str:
    res = client.post("/api/v1/sessions", json={"user_meta": {"display_name": "Tester"}})
    assert res.status_code == 201
    return res.json()["id"]


def ask(client: TestClient, session_id: str, content: str, **extra: Any) -> list[tuple[str, Any]]:
    res = client.post(f"/api/v1/sessions/{session_id}/messages", json={"content": content, **extra})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")
    events = []
    for block in res.text.strip().split("\n\n"):
        name, data = block.split("\n", 1)
        events.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return events
