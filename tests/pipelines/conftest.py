"""Fixtures for tests that need a real PostgreSQL database.

They run only when TEST_DATABASE_URL points at a disposable database (CI provides one) and are skipped
otherwise. The project's schemas are dropped and rebuilt from sql/, so never point it at a real database.
TEST_DATABASE_URL must connect as a superuser. The schemas are built as in production (doadmin runs the create
and permission files), and tests run as showdown-analyst, so a missing grant fails them.
"""

import os
from pathlib import Path

import psycopg
import pytest
from psycopg import sql

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
    "create/raw/usage_report.sql",
    "create/raw/usage_pokemon.sql",
    "create/raw/leads_report.sql",
    "create/raw/leads_pokemon.sql",
    "create/raw/metagame_report.sql",
    "create/raw/metagame_tag.sql",
    "create/raw/matchup_chart_report.sql",
    "create/raw/matchup_chart_cell.sql",
    "create/raw/matchup_chart_viability.sql",
    "create/raw/ingestion_run.sql",
    "create/raw/replay.sql",
    "index/raw/replay.sql",
    "create/raw/replay_collection_run.sql",
    "create/staging/schema.sql",
    "create/api/schema.sql",
]
PERMISSION_FILES = ["permissions/showdown_analyst.sql", "permissions/showdown_transform.sql"]
ROLES = ["doadmin", "showdown-analyst", "showdown-transform"]
PROTECTED_DATABASES = {"showdown-database", "defaultdb"}


@pytest.fixture(scope="session")
def database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set")
    return url


@pytest.fixture(scope="session")
def schemas(database_url: str) -> None:
    with psycopg.connect(database_url, autocommit=True) as conn:
        if conn.info.dbname in PROTECTED_DATABASES:
            raise RuntimeError(f"Refusing to rebuild schemas in {conn.info.dbname}")
        conn.execute("DROP SCHEMA IF EXISTS api, staging, raw, reference CASCADE")
        existing = {row[0] for row in conn.execute("SELECT rolname FROM pg_roles WHERE rolname = ANY(%s)", (ROLES,))}
        for role in ROLES:
            if role not in existing:
                conn.execute(sql.SQL("CREATE ROLE {}").format(sql.Identifier(role)))
        # doadmin owns the database, as in production, so the permission files can grant and revoke CONNECT on it.
        conn.execute(sql.SQL("ALTER DATABASE {} OWNER TO doadmin").format(sql.Identifier(conn.info.dbname)))
        # showdown_analyst.sql revokes CONNECT on defaultdb, so it has to exist.
        if conn.execute("SELECT 1 FROM pg_database WHERE datname = 'defaultdb'").fetchone() is None:
            conn.execute("CREATE DATABASE defaultdb")
        # Run as doadmin, as in production, so its default privileges apply to the tables it creates.
        conn.execute("SET ROLE doadmin")
        for name in SQL_FILES + PERMISSION_FILES:
            conn.execute((SQL_DIR / name).read_bytes())


@pytest.fixture
def conn(database_url: str, schemas: None):
    """A connection as showdown-analyst, the pipelines' role, whose changes are rolled back after each test."""
    with psycopg.connect(database_url) as connection:
        connection.execute('SET ROLE "showdown-analyst"')
        yield connection
        connection.rollback()
