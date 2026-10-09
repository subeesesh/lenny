import math
import re
import zlib
from collections.abc import AsyncIterator

from app.errors import AppError
from app.llm.base import Message, ProviderTimeout

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
