"""Fixtures for the API tests, which run against the test database as showdown-api.

The database fixtures come from tests/pipelines/conftest.py, which builds the schemas and runs the permission
files, so the API is tested with the same grants it has in production.
"""

import importlib.util
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg_pool import ConnectionPool

from api.main import create_app

_PIPELINES_CONFTEST = Path(__file__).parents[1] / "pipelines" / "conftest.py"
_spec = importlib.util.spec_from_file_location("pipelines_conftest", _PIPELINES_CONFTEST)
assert _spec and _spec.loader
_pipelines_conftest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_pipelines_conftest)

database_url = _pipelines_conftest.database_url
schemas = _pipelines_conftest.schemas


def _as_api_role(conn: psycopg.Connection) -> None:
    # The test server's roles can't log in, so connect as the superuser and switch to showdown-api.
    conn.execute('SET ROLE "showdown-api"')
    conn.commit()


@pytest.fixture
def client(database_url: str, schemas: None) -> Iterator[TestClient]:
    pool = ConnectionPool(database_url, min_size=1, max_size=1, configure=_as_api_role, open=False)
    with TestClient(create_app(pool)) as test_client:
        yield test_client
