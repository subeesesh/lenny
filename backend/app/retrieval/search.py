from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import httpx
import structlog
from psycopg_pool import AsyncConnectionPool

from app.llm.ollama import KEEP_ALIVE
from app.retrieval import guards

QueryEmbedder = Callable[[str], Awaitable[list[float]]]

QUERY_PREFIX = "search_query: "
CANDIDATES = 15
PER_EPISODE = 4
EMPTY_MESSAGE = "The transcripts don't cover this."

log = structlog.get_logger()


@dataclass
class Hit:
    chunk_id: int
    slug: str
    title: str
    guest: str | None
    url: str | None
    ts: str | None
    speaker: str | None
    text: str
    score: float


@dataclass
class Retrieval:
    hits: list[Hit] = field(default_factory=list)
    refusal: str | None = None
    reason: str | None = None
    top_score: float | None = None


def ollama_query_embedder(base_url: str, model: str, timeout_s: float = 30) -> QueryEmbedder:
    async def embed(text: str) -> list[float]:
        async with httpx.AsyncClient(base_url=base_url, timeout=timeout_s) as client:
            body = {"model": model, "input": [QUERY_PREFIX + text], "keep_alive": KEEP_ALIVE}
            res = await client.post("/api/embed", json=body)
            res.raise_for_status()
            return res.json()["embeddings"][0]

    return embed


def query_text(question: str, previous: str | None) -> str:
    return f"{previous}\n{question}" if previous else question


def diversify(hits: list[Hit], top_k: int) -> list[Hit]:
    per_episode: dict[str, int] = {}
    kept = []
    for hit in hits:
        if per_episode.get(hit.slug, 0) < PER_EPISODE:
            per_episode[hit.slug] = per_episode.get(hit.slug, 0) + 1
            kept.append(hit)
    return kept[:top_k]


async def nearest(pool: AsyncConnectionPool, vector: list[float]) -> list[Hit]:
    q = str(vector)
    async with pool.connection() as conn:
        cur = await conn.execute(
            """SELECT c.id, e.slug, e.title, e.guest, e.url, c.start_ts, c.speaker, c.text,
                      1 - (c.embedding <=> %s::vector) AS score
               FROM chunks c JOIN episodes e ON e.id = c.episode_id
               ORDER BY c.embedding <=> %s::vector LIMIT %s""",
            (q, q, CANDIDATES),
        )
        return [Hit(*row) for row in await cur.fetchall()]


async def known_people(pool: AsyncConnectionPool) -> list[str]:
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT guest FROM episodes WHERE guest IS NOT NULL UNION SELECT DISTINCT speaker FROM chunks WHERE speaker IS NOT NULL"
        )
        return [row[0] for row in await cur.fetchall()]


async def retrieve(
    pool: AsyncConnectionPool,
    embed: QueryEmbedder,
    question: str,
    previous: str | None,
    top_k: int,
    min_score: float,
) -> Retrieval:
    if guards.is_personal_data_request(question):
        log.info("retrieval_refused", reason="personal_data")
        return Retrieval(refusal=guards.PERSONAL_DATA_MESSAGE, reason="personal_data")
    name = guards.asked_person(question)
    if name and not guards.is_known_person(name, await known_people(pool)):
        log.info("retrieval_refused", reason="not_a_guest")
        return Retrieval(refusal=guards.non_guest_message(name), reason="not_a_guest")
    hits = diversify(await nearest(pool, await embed(query_text(question, previous))), top_k)
    top = hits[0].score if hits else None
    if top is None or top < min_score:
        log.info("retrieval_empty", retrieval_top_score=top)
        return Retrieval(refusal=EMPTY_MESSAGE, reason="retrieval_empty", top_score=top)
    return Retrieval(hits=hits, top_score=top)

