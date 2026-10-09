from pathlib import Path

from psycopg_pool import AsyncConnectionPool

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schema.sql"


def create_pool(database_url: str) -> AsyncConnectionPool:
    return AsyncConnectionPool(database_url, min_size=1, max_size=10, open=False, timeout=5)


async def apply_schema(pool: AsyncConnectionPool) -> None:
    async with pool.connection() as conn:
        await conn.execute(SCHEMA_PATH.read_text())


async def count_chunks(pool: AsyncConnectionPool) -> int:
    async with pool.connection() as conn:
        cur = await conn.execute("SELECT count(*) FROM chunks")
        row = await cur.fetchone()
    return row[0]
