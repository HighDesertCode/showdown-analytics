"""Fixtures for tests that need a real PostgreSQL database.

They run only when TEST_DATABASE_URL points at a disposable database (CI provides one) and are skipped
otherwise. The reference schema is dropped and rebuilt from sql/, so never point it at a real database.
"""

import os
from pathlib import Path

import psycopg
import pytest

SQL_DIR = Path(__file__).resolve().parents[2] / "sql"
# Foreign-key order; the same order used to run these files manually against showdown-database.
SQL_FILES = [
    "create/reference/schema.sql",
    "create/reference/type.sql",
    "create/reference/species.sql",
    "create/reference/ability.sql",
    "create/reference/species_ability.sql",
    "create/reference/move.sql",
    "create/reference/move_effect.sql",
    "create/reference/item.sql",
    "create/reference/nature.sql",
    "index/reference/species_ability.sql",
    "create/raw/schema.sql",
    "create/raw/source_file.sql",
    "create/raw/chaos_report.sql",
    "create/raw/chaos_pokemon.sql",
    "create/raw/chaos_option.sql",
    "create/raw/chaos_counter.sql",
]
PROTECTED_DATABASES = {"showdown-database", "defaultdb"}


@pytest.fixture(scope="session")
def database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set")
    return url


@pytest.fixture(scope="session")
def reference_schema(database_url: str) -> None:
    with psycopg.connect(database_url, autocommit=True) as conn:
        if conn.info.dbname in PROTECTED_DATABASES:
            raise RuntimeError(f"Refusing to rebuild the reference schema in {conn.info.dbname}")
        conn.execute("DROP SCHEMA IF EXISTS reference CASCADE")
        for name in SQL_FILES:
            conn.execute((SQL_DIR / name).read_bytes())


@pytest.fixture
def conn(database_url: str, reference_schema: None):
    """A connection whose changes are rolled back after each test."""
    with psycopg.connect(database_url) as connection:
        yield connection
        connection.rollback()
