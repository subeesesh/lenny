from fastapi.testclient import TestClient

from app.db.pool import create_pool


def test_health(client: TestClient) -> None:
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
    assert res.headers["X-Request-ID"]


def test_ready_with_db_up(client: TestClient) -> None:
    res = client.get("/api/v1/ready")
    assert res.status_code == 200
    body = res.json()
    assert body["db"] is True
    assert isinstance(body["chunks"], int)
    assert set(body) == {"db", "ollama", "anthropic_key", "chunks"}


def test_ready_with_db_down_returns_503(client: TestClient) -> None:
    client.app.state.pool = create_pool("postgresql://nobody:x@127.0.0.1:1/none")
    client.portal.call(client.app.state.pool.open, False)
    try:
        res = client.get("/api/v1/ready")
    finally:
        client.portal.call(client.app.state.pool.close)
    assert res.status_code == 503
    assert res.json()["db"] is False
    assert res.json()["chunks"] is None
