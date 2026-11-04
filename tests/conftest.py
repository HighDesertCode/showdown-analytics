"""Fixtures for tests that need a real PostgreSQL database, shared by every product's tests.

They run only when TEST_DATABASE_URL points at a disposable database (CI provides one) and are skipped otherwise. The
project's schemas are dropped and rebuilt from sql/, so never point it at a real database. TEST_DATABASE_URL must
connect as a superuser. The schemas are built as in production (doadmin runs the create and permission files), and
each product's tests then run as its own role, so a missing grant fails them.
"""

import os

import psycopg
import pytest
from psycopg import sql

from tests.database import PERMISSION_FILES, PROTECTED_DATABASES, ROLES, SQL_DIR, SQL_FILES


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
        # As in production, doadmin can create roles and administers the project's roles, so the permission files can
        # set default privileges for showdown-transform and limits on showdown-api.
        conn.execute("ALTER ROLE doadmin CREATEROLE")
        for role in ROLES[1:]:
            conn.execute(sql.SQL("GRANT {} TO doadmin WITH ADMIN OPTION").format(sql.Identifier(role)))
        # doadmin owns the database, as in production, so the permission files can grant and revoke CONNECT on it.
        conn.execute(sql.SQL("ALTER DATABASE {} OWNER TO doadmin").format(sql.Identifier(conn.info.dbname)))
        # showdown_analyst.sql revokes CONNECT on defaultdb, so it has to exist.
        if conn.execute("SELECT 1 FROM pg_database WHERE datname = 'defaultdb'").fetchone() is None:
            conn.execute("CREATE DATABASE defaultdb")
        # Run as doadmin, as in production, so its default privileges apply to the tables it creates.
        conn.execute("SET ROLE doadmin")
        for name in SQL_FILES + PERMISSION_FILES:
            conn.execute((SQL_DIR / name).read_bytes())
