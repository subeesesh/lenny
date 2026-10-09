from collections.abc import Callable

import httpx

Embedder = Callable[[list[str]], list[list[float]]]

DOC_PREFIX = "search_document: "
BATCH_SIZE = 32


def ollama_embedder(base_url: str, model: str, timeout_s: float = 120) -> Embedder:
    client = httpx.Client(base_url=base_url, timeout=timeout_s)

    def embed(texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for i in range(0, len(texts), BATCH_SIZE):
            batch = [DOC_PREFIX + t for t in texts[i : i + BATCH_SIZE]]
            res = client.post("/api/embed", json={"model": model, "input": batch})
            res.raise_for_status()
            vectors.extend(res.json()["embeddings"])
        return vectors

    return embed
