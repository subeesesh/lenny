from dataclasses import dataclass
from pathlib import Path

import numpy as np
import psycopg
import structlog

from app.ingest.chunk import Chunk, chunk_turns
from app.ingest.clean import clean_turns, split_turns
from app.ingest.embed import Embedder
from app.ingest.source import NON_EPISODES, Episode, load_episodes, select_episodes

log = structlog.get_logger()


@dataclass
class Summary:
    files: int = 0
    non_episodes: int = 0
    duplicates: int = 0
    ingested: int = 0
    skipped_unchanged: int = 0
    sponsor_paragraphs: int = 0
    chunks: int = 0
    failures: int = 0

    def __str__(self) -> str:
        return "\n".join(f"{k:<20} {v}" for k, v in vars(self).items())


def existing_hashes(conn: psycopg.Connection) -> dict[str, str]:
    return dict(conn.execute("SELECT slug, content_hash FROM episodes").fetchall())


def save_episode(conn: psycopg.Connection, ep: Episode, chunks: list[Chunk], vectors: list[list[float]]) -> None:
    with conn.transaction():
        row = conn.execute(
            """INSERT INTO episodes (slug, title, guest, url, published_at, content_hash)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT (slug) DO UPDATE SET title = EXCLUDED.title, guest = EXCLUDED.guest,
                 url = EXCLUDED.url, published_at = EXCLUDED.published_at,
                 content_hash = EXCLUDED.content_hash, ingested_at = now()
               RETURNING id""",
            (ep.slug, ep.title, ep.guest, ep.url, ep.published_at, ep.content_hash),
        ).fetchone()
        conn.execute("DELETE FROM chunks WHERE episode_id = %s", (row[0],))
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO chunks (episode_id, ord, speaker, start_ts, text, embedding) VALUES (%s, %s, %s, %s, %s, %s)",
                [(row[0], c.ord, c.speaker, c.start_ts, c.text, np.array(v)) for c, v in zip(chunks, vectors)],
            )


def ingest_episode(conn: psycopg.Connection, ep: Episode, embed: Embedder) -> tuple[int, int]:
    turns, sponsor = clean_turns(split_turns(ep.body))
    chunks = chunk_turns(turns)
    if not chunks:
        raise ValueError("no transcript text after cleaning")
    save_episode(conn, ep, chunks, embed([c.text for c in chunks]))
    return len(chunks), sponsor


def run(conn: psycopg.Connection, episodes_dir: Path, embed: Embedder, limit: int | None = None) -> Summary:
    episodes = load_episodes(episodes_dir)
    kept, duplicates = select_episodes(episodes)
    summary = Summary(
        files=len(episodes),
        non_episodes=sum(ep.slug in NON_EPISODES for ep in episodes),
        duplicates=duplicates,
    )
    seen = existing_hashes(conn)
    for ep in kept[:limit]:
        if seen.get(ep.slug) == ep.content_hash:
            summary.skipped_unchanged += 1
            continue
        try:
            chunks, sponsor = ingest_episode(conn, ep, embed)
        except Exception as exc:
            summary.failures += 1
            log.error("ingest_failed", slug=ep.slug, error=f"{type(exc).__name__}: {exc}")
            continue
        summary.ingested += 1
        summary.chunks += chunks
        summary.sponsor_paragraphs += sponsor
        log.info("episode_ingested", slug=ep.slug, chunks=chunks)
    return summary
