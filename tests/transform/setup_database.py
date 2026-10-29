"""Sets up a disposable PostgreSQL database like showdown-database, so CI can run dbt against it.

Creates the project's roles, then runs every file in sql/ as doadmin, in the order the pipelines tests use.
Run it with TEST_DATABASE_URL set to a superuser connection on a throwaway server; never a real database.
"""

import importlib.util
import os
from pathlib import Path

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[2]
PERMISSION_FILES = ["permissions/showdown_analyst.sql", "permissions/showdown_transform.sql"]
PROTECTED_DATABASES = {"showdown-database", "defaultdb"}
# Throwaway passwords for a CI-only server; the workflow passes the same values to dbt.
ROLES = {"doadmin": "doadmin", "showdown-analyst": "analyst", "showdown-transform": "transform"}


def sql_files() -> list[str]:
    """The create and index order, from tests/pipelines/conftest.py, so it is defined in one place."""
    spec = importlib.util.spec_from_file_location("conftest", ROOT / "tests/pipelines/conftest.py")
    assert spec and spec.loader
    conftest = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(conftest)
    return conftest.SQL_FILES


def main() -> None:
    url = os.environ["TEST_DATABASE_URL"]
    with psycopg.connect(url, autocommit=True) as conn:
        database = conn.info.dbname
        if database in PROTECTED_DATABASES:
            raise RuntimeError(f"Refusing to set up {database}")
        for role, password in ROLES.items():
            conn.execute(
                sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(role), sql.Literal(password))
            )
        conn.execute(sql.SQL("GRANT CREATE ON DATABASE {} TO doadmin").format(sql.Identifier(database)))
        # showdown_analyst.sql revokes CONNECT on defaultdb, so it has to exist.
        conn.execute("CREATE DATABASE defaultdb OWNER doadmin")

    # Run as doadmin, as in production, so its default privileges apply to the tables it creates.
    with psycopg.connect(url, user="doadmin", password=ROLES["doadmin"], autocommit=True) as conn:
        for name in sql_files() + PERMISSION_FILES:
            conn.execute((ROOT / "sql" / name).read_bytes())
    print(f"Set up {database} with {len(ROLES)} roles")


if __name__ == "__main__":
    main()
