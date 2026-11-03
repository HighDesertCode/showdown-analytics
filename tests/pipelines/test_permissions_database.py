"""Checks database-level privileges from sql/permissions/ (see tests/pipelines/conftest.py)."""

import psycopg
import pytest


@pytest.mark.parametrize(
    ("role", "privilege", "expected"),
    [
        ("public", "CONNECT", False),
        ("public", "TEMPORARY", False),
        ("showdown-analyst", "CONNECT", True),
        ("showdown-analyst", "TEMPORARY", False),
        ("showdown-transform", "CONNECT", True),
        ("showdown-transform", "TEMPORARY", True),
        ("showdown-api", "CONNECT", True),
        ("showdown-api", "TEMPORARY", False),
    ],
)
def test_only_project_roles_can_use_the_database(conn, role, privilege, expected):
    row = conn.execute("SELECT HAS_DATABASE_PRIVILEGE(%s, CURRENT_DATABASE(), %s)", (role, privilege)).fetchone()

    assert row == (expected,)


@pytest.mark.parametrize(
    ("schema", "expected"),
    [("api", True), ("reference", False), ("raw", False), ("staging", False)],
)
def test_api_role_can_use_only_the_api_schema(conn, schema, expected):
    row = conn.execute("SELECT HAS_SCHEMA_PRIVILEGE('showdown-api', %s, 'USAGE')", (schema,)).fetchone()

    assert row == (expected,)


def test_api_role_can_read_but_not_write_tables_dbt_builds(database_url, schemas):
    with psycopg.connect(database_url) as conn:
        conn.execute('SET ROLE "showdown-transform"')
        conn.execute("CREATE TABLE api.permission_check (id INTEGER)")
        row = conn.execute(
            """
            SELECT HAS_TABLE_PRIVILEGE('showdown-api', 'api.permission_check', 'SELECT'),
                   HAS_TABLE_PRIVILEGE('showdown-api', 'api.permission_check', 'INSERT, UPDATE, DELETE, TRUNCATE')
            """
        ).fetchone()
        conn.rollback()

    assert row == (True, False)


def test_api_role_has_limits(conn):
    row = conn.execute("SELECT rolconnlimit, rolconfig FROM pg_roles WHERE rolname = 'showdown-api'").fetchone()

    assert row == (10, ["statement_timeout=5s"])
