from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pgvector.psycopg import register_vector
from psycopg.conninfo import make_conninfo

from app.config import get_settings
from app.db.pool import SCHEMA_PATH
from app.ingest.pipeline import run
from app.main import create_app
from tests.fakes import bag_of_words

EPISODES = Path(__file__).parent / "fixtures" / "episodes"
TEST_DB = "lenny_test"


@pytest.fixture(scope="session")
def test_db_url() -> Iterator[str]:
    """A separate database filled from the fixture transcripts, so tests never touch real data."""
    admin_url = get_settings().database_url
    url = make_conninfo(admin_url, dbname=TEST_DB)
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
        admin.execute(f"CREATE DATABASE {TEST_DB}")
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(SCHEMA_PATH.read_text())
        register_vector(conn)
        run(conn, EPISODES, lambda texts: [bag_of_words(t) for t in texts])
    yield url
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")


@pytest.fixture
def app(test_db_url: str) -> FastAPI:
    return create_app(test_db_url)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
