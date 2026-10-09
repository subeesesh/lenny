from typing import Any
from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

Row = dict[str, Any]
SESSION_COLS = "id, title, user_meta, created_at, updated_at"
MESSAGE_COLS = "id, role, content, route, citations, provider, model, status, latency_ms, created_at"


async def fetch_all(pool: AsyncConnectionPool, sql: str, params: tuple[Any, ...] = ()) -> list[Row]:
    async with pool.connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(sql, params)
        return await cur.fetchall()


async def fetch_one(pool: AsyncConnectionPool, sql: str, params: tuple[Any, ...] = ()) -> Row | None:
    rows = await fetch_all(pool, sql, params)
    return rows[0] if rows else None


async def create_session(pool: AsyncConnectionPool, user_meta: dict[str, Any]) -> Row:
    row = await fetch_one(pool, f"INSERT INTO sessions (user_meta) VALUES (%s) RETURNING {SESSION_COLS}", (Jsonb(user_meta),))
    assert row is not None
    return row


async def list_sessions(pool: AsyncConnectionPool) -> list[Row]:
    return await fetch_all(pool, f"SELECT {SESSION_COLS} FROM sessions ORDER BY updated_at DESC")


async def get_session(pool: AsyncConnectionPool, session_id: UUID) -> Row | None:
    return await fetch_one(pool, f"SELECT {SESSION_COLS} FROM sessions WHERE id = %s", (session_id,))


async def list_messages(pool: AsyncConnectionPool, session_id: UUID) -> list[Row]:
    return await fetch_all(
        pool, f"SELECT {MESSAGE_COLS} FROM messages WHERE session_id = %s ORDER BY id", (session_id,)
    )


async def list_artifacts(pool: AsyncConnectionPool, session_id: UUID) -> list[Row]:
    return await fetch_all(
        pool,
        "SELECT id, message_id, type, title, created_at FROM artifacts WHERE session_id = %s ORDER BY created_at",
        (session_id,),
    )


async def recent_messages(pool: AsyncConnectionPool, session_id: UUID, limit: int) -> list[Row]:
    rows = await fetch_all(
        pool,
        "SELECT role, content FROM messages WHERE session_id = %s AND status = 'complete' ORDER BY id DESC LIMIT %s",
        (session_id, limit),
    )
    return rows[::-1]


async def add_user_message(pool: AsyncConnectionPool, session_id: UUID, content: str) -> int:
    async with pool.connection() as conn:
        cur = await conn.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (%s, 'user', %s) RETURNING id", (session_id, content)
        )
        row = await cur.fetchone()
        await conn.execute(
            """UPDATE sessions SET updated_at = now(),
                 title = CASE WHEN title = 'New chat' THEN left(%s, 60) ELSE title END
               WHERE id = %s""",
            (content, session_id),
        )
    assert row is not None
    return row[0]


async def add_assistant_message(
    pool: AsyncConnectionPool,
    session_id: UUID,
    content: str,
    route: str,
    citations: list[dict[str, Any]],
    provider: str | None,
    model: str | None,
    status: str,
    latency_ms: int,
) -> int:
    async with pool.connection() as conn:
        cur = await conn.execute(
            """INSERT INTO messages (session_id, role, content, route, citations, provider, model, status, latency_ms)
               VALUES (%s, 'assistant', %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (session_id, content, route, Jsonb(citations), provider, model, status, latency_ms),
        )
        row = await cur.fetchone()
        await conn.execute("UPDATE sessions SET updated_at = now() WHERE id = %s", (session_id,))
    assert row is not None
    return row[0]


async def add_artifact(
    pool: AsyncConnectionPool, session_id: UUID, message_id: int, type_: str, title: str, content: str
) -> Row:
    row = await fetch_one(
        pool,
        """INSERT INTO artifacts (session_id, message_id, type, title, content) VALUES (%s, %s, %s, %s, %s)
           RETURNING id, type, title""",
        (session_id, message_id, type_, title, content),
    )
    assert row is not None
    return row


async def get_artifact(pool: AsyncConnectionPool, artifact_id: UUID, session_id: UUID) -> Row | None:
    return await fetch_one(
        pool,
        """SELECT id, session_id, message_id, type, title, content, created_at FROM artifacts
           WHERE id = %s AND session_id = %s""",
        (artifact_id, session_id),
    )
