"""Fixtures for the API tests, which run against the test database as showdown-api.

The database fixtures come from tests/pipelines/conftest.py, which builds the schemas and runs the permission
files, so the API is tested with the same grants it has in production. The api tables are created from the dbt
models' contracts, so a query that uses a column the contract doesn't publish fails here.
"""

import importlib.util
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, LiteralString, cast

import psycopg
import pytest
import yaml
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg_pool import ConnectionPool

from api.main import create_app

ROOT = Path(__file__).parents[2]
API_MODELS = ROOT / "transform" / "models" / "api"

_spec = importlib.util.spec_from_file_location("pipelines_conftest", ROOT / "tests" / "pipelines" / "conftest.py")
assert _spec and _spec.loader
_pipelines_conftest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_pipelines_conftest)

database_url = _pipelines_conftest.database_url
schemas = _pipelines_conftest.schemas

Insert = Callable[..., None]


def api_contracts() -> dict[str, list[tuple[str, str]]]:
    """Each api model's columns and types, from its YAML contract."""
    contracts = {}
    for path in sorted(API_MODELS.rglob("*.yml")):
        if path.name.endswith("_unit_tests.yml"):
            continue
        for model in yaml.safe_load(path.read_text()).get("models", []):
            contracts[model["name"]] = [(column["name"], column["data_type"]) for column in model["columns"]]
    return contracts


@pytest.fixture(scope="session")
def api_tables(database_url: str, schemas: None) -> list[str]:
    """Creates every api model as an empty table, as showdown-transform, as dbt does in production.

    The column types come from the repo's own contracts, so they're trusted as SQL.
    """
    contracts = api_contracts()
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute('SET ROLE "showdown-transform"')
        for name, columns in contracts.items():
            table = sql.Identifier("api", name)
            conn.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(table))
            definitions = sql.SQL(", ").join(
                sql.SQL("{} {}").format(sql.Identifier(column), sql.SQL(cast(LiteralString, data_type.upper())))
                for column, data_type in columns
            )
            conn.execute(sql.SQL("CREATE TABLE {} ({})").format(table, definitions))
    return list(contracts)


@pytest.fixture
def insert(database_url: str, api_tables: list[str]) -> Iterator[Insert]:
    """Inserts a row into an api table; every api table is emptied after the test."""
    with psycopg.connect(database_url, autocommit=True) as conn:

        def insert_row(table: str, **values: Any) -> None:
            conn.execute(
                sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                    sql.Identifier("api", table),
                    sql.SQL(", ").join(map(sql.Identifier, values)),
                    sql.SQL(", ").join(sql.Placeholder() * len(values)),
                ),
                list(values.values()),
            )

        yield insert_row
        conn.execute(
            sql.SQL("TRUNCATE {}").format(sql.SQL(", ").join(sql.Identifier("api", table) for table in api_tables))
        )


def _as_api_role(conn: psycopg.Connection) -> None:
    # The test server's roles can't log in, so connect as the superuser and switch to showdown-api.
    conn.execute('SET ROLE "showdown-api"')
    conn.commit()


@pytest.fixture
def client(database_url: str, api_tables: list[str]) -> Iterator[TestClient]:
    pool = ConnectionPool(database_url, min_size=1, max_size=1, configure=_as_api_role, open=False)
    with TestClient(create_app(pool)) as test_client:
        yield test_client
