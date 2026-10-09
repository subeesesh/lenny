from collections.abc import Callable
from typing import Any

import httpx
import psycopg
from fastapi import FastAPI
from fastapi.testclient import TestClient


def assert_error(res: httpx.Response, status: int, code: str) -> None:
    assert res.status_code == status
    body = res.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "request_id"}
    assert body["error"]["code"] == code
    assert body["error"]["message"]
    assert body["error"]["request_id"] == res.headers["X-Request-ID"]


def add_route(app: FastAPI, path: str, endpoint: Callable[..., Any]) -> None:
    """Register a test-only route ahead of the static UI mount at "/"."""
    app.add_api_route(path, endpoint)
    app.router.routes.insert(0, app.router.routes.pop())


def test_not_found_shape(client: TestClient) -> None:
    assert_error(client.get("/api/v1/nope"), 404, "not_found")


def test_validation_error_shape(app: FastAPI) -> None:
    async def needs_int(n: int) -> dict[str, int]:
        return {"n": n}

    add_route(app, "/test/int", needs_int)

    with TestClient(app) as client:
        assert_error(client.get("/test/int?n=abc"), 422, "validation_error")


def test_db_error_shape(app: FastAPI) -> None:
    async def db_down() -> None:
        raise psycopg.OperationalError("connection refused")

    add_route(app, "/test/db", db_down)

    with TestClient(app) as client:
        assert_error(client.get("/test/db"), 503, "db_unavailable")


def test_unhandled_error_shape(app: FastAPI) -> None:
    async def boom() -> None:
        raise RuntimeError("boom")

    add_route(app, "/test/boom", boom)

    with TestClient(app, raise_server_exceptions=False) as client:
        assert_error(client.get("/test/boom"), 500, "internal_error")


def test_request_id_is_echoed(client: TestClient) -> None:
    res = client.get("/api/v1/nope", headers={"X-Request-ID": "abc123"})
    assert res.json()["error"]["request_id"] == "abc123"
