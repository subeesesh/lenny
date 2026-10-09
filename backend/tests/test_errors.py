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


def test_not_found_shape(client: TestClient) -> None:
    assert_error(client.get("/api/v1/nope"), 404, "not_found")


def test_validation_error_shape(app: FastAPI) -> None:
    @app.get("/test/int")
    async def needs_int(n: int) -> dict[str, int]:
        return {"n": n}

    with TestClient(app) as client:
        assert_error(client.get("/test/int?n=abc"), 422, "validation_error")


def test_db_error_shape(app: FastAPI) -> None:
    @app.get("/test/db")
    async def db_down() -> None:
        raise psycopg.OperationalError("connection refused")

    with TestClient(app) as client:
        assert_error(client.get("/test/db"), 503, "db_unavailable")


def test_unhandled_error_shape(app: FastAPI) -> None:
    @app.get("/test/boom")
    async def boom() -> None:
        raise RuntimeError("boom")

    with TestClient(app, raise_server_exceptions=False) as client:
        assert_error(client.get("/test/boom"), 500, "internal_error")


def test_request_id_is_echoed(client: TestClient) -> None:
    res = client.get("/api/v1/nope", headers={"X-Request-ID": "abc123"})
    assert res.json()["error"]["request_id"] == "abc123"
