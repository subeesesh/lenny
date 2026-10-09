import json
import time
from collections.abc import AsyncIterator
from typing import Annotated, Any, Literal
from uuid import UUID

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, StringConstraints

from app.agent.skills import TurnResult, run_turn
from app.db import repo
from app.errors import AppError

router = APIRouter()
log = structlog.get_logger()
HISTORY_MESSAGES = 2


class UserMeta(BaseModel):
    display_name: str = Field("", max_length=60)


class SessionCreate(BaseModel):
    user_meta: UserMeta = UserMeta()


class MessageCreate(BaseModel):
    content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
    route_hint: Literal["essay", "artifact"] | None = None


async def require_session(request: Request, session_id: UUID) -> dict[str, Any]:
    session = await repo.get_session(request.app.state.pool, session_id)
    if session is None:
        raise AppError("not_found", "Session not found.")
    return session


@router.post("/sessions", status_code=201)
async def create_session(body: SessionCreate, request: Request) -> dict[str, Any]:
    row = await repo.create_session(request.app.state.pool, body.user_meta.model_dump())
    return {"id": row["id"], "title": row["title"], "created_at": row["created_at"]}


@router.get("/sessions")
async def list_sessions(request: Request) -> list[dict[str, Any]]:
    return await repo.list_sessions(request.app.state.pool)


@router.get("/sessions/{session_id}")
async def get_session(session_id: UUID, request: Request) -> dict[str, Any]:
    session = await require_session(request, session_id)
    pool = request.app.state.pool
    return {
        **session,
        "messages": await repo.list_messages(pool, session_id),
        "artifacts": await repo.list_artifacts(pool, session_id),
    }


def sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@router.post("/sessions/{session_id}/messages")
async def post_message(session_id: UUID, body: MessageCreate, request: Request) -> StreamingResponse:
    await require_session(request, session_id)
    state = request.app.state
    history = await repo.recent_messages(state.pool, session_id, HISTORY_MESSAGES)
    await repo.add_user_message(state.pool, session_id, body.content)
    structlog.contextvars.bind_contextvars(session_id=str(session_id))
    request_id = request.state.request_id

    async def events() -> AsyncIterator[str]:
        start = time.perf_counter()
        result = TurnResult()
        error: AppError | None = None
        try:
            turn = run_turn(body.content, body.route_hint, history, state.retriever, state.provider_factory, state.skills, result)
            async for event, data in turn:
                yield sse(event, data)
        except AppError as exc:
            error = exc
        except Exception:
            log.exception("internal_error", error_code="internal_error")
            error = AppError("internal_error", "Something went wrong while answering.")
        latency_ms = int((time.perf_counter() - start) * 1000)
        message_id = await repo.add_assistant_message(
            state.pool, session_id, result.text, result.route, result.citations,
            result.provider, result.model, "error" if error else "complete", latency_ms,
        )
        log.info(
            "turn_done", route=result.route, provider=result.provider, model=result.model,
            latency_ms=latency_ms, error_code=error.code if error else None,
        )
        if error:
            yield sse("error", error.to_dict(request_id))
        else:
            yield sse("done", {"message_id": message_id, "provider": result.provider, "model": result.model, "latency_ms": latency_ms})

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
