import argparse
from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector

from app.config import get_settings
from app.db.pool import SCHEMA_PATH
from app.ingest.embed import ollama_embedder
from app.ingest.pipeline import run
from app.ingest.source import ensure_source
from app.logging import configure_logging

SOURCE_DIR = Path("data/transcripts")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Lenny's Podcast transcripts.")
    parser.add_argument("--limit", type=int, default=None, help="only process the first N kept episodes")
    args = parser.parse_args()
    settings = get_settings()
    configure_logging(settings.log_level)
    ensure_source(SOURCE_DIR)
    embed = ollama_embedder(settings.ollama_base_url, settings.embed_model)
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute(SCHEMA_PATH.read_text())
        register_vector(conn)
        summary = run(conn, SOURCE_DIR / "episodes", embed, args.limit)
        total = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
    print(summary)
    print(f"{'chunks_in_db':<20} {total}")


if __name__ == "__main__":
    main()
