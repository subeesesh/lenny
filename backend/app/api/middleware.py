import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response

log = structlog.get_logger()


async def request_id_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    request.state.request_id = request_id
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    log.info(
        "request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        latency_ms=int((time.perf_counter() - start) * 1000),
    )
    return response
