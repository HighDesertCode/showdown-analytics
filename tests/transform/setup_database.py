"""Sets up a disposable PostgreSQL database like showdown-database, so CI can run dbt against it.

Creates the project's roles, then runs every file in sql/ as doadmin, in the order tests/database.py gives.
Run it with TEST_DATABASE_URL set to a superuser connection on a throwaway server; never a real database.
"""

import os
import sys
from pathlib import Path

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[2]
# Throwaway passwords for a CI-only server; the workflow passes the same values to dbt.
ROLES = {"doadmin": "doadmin", "showdown-analyst": "analyst", "showdown-transform": "transform", "showdown-api": "api"}


def main() -> None:
    # Run as a script, so the repo root isn't on the path by itself.
    sys.path.insert(0, str(ROOT))
    from tests.database import PERMISSION_FILES, PROTECTED_DATABASES, SQL_FILES

    url = os.environ["TEST_DATABASE_URL"]
    with psycopg.connect(url, autocommit=True) as conn:
        database = conn.info.dbname
        if database in PROTECTED_DATABASES:
            raise RuntimeError(f"Refusing to set up {database}")
        for role, password in ROLES.items():
            conn.execute(
                sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(role), sql.Literal(password))
            )
        # As in production, doadmin can create roles and administers the project's roles, so the permission files can
        # set default privileges for showdown-transform and limits on showdown-api.
        conn.execute("ALTER ROLE doadmin CREATEROLE")
        for role in list(ROLES)[1:]:
            conn.execute(sql.SQL("GRANT {} TO doadmin WITH ADMIN OPTION").format(sql.Identifier(role)))
        # doadmin owns the database, as in production, so the permission files can grant and revoke CONNECT on it.
        conn.execute(sql.SQL("ALTER DATABASE {} OWNER TO doadmin").format(sql.Identifier(database)))
        # showdown_analyst.sql revokes CONNECT on defaultdb, so it has to exist.
        conn.execute("CREATE DATABASE defaultdb OWNER doadmin")

    # Run as doadmin, as in production, so its default privileges apply to the tables it creates.
    with psycopg.connect(url, user="doadmin", password=ROLES["doadmin"], autocommit=True) as conn:
        for name in SQL_FILES + PERMISSION_FILES:
            conn.execute((ROOT / "sql" / name).read_bytes())
    print(f"Set up {database} with {len(ROLES)} roles")


if __name__ == "__main__":
    main()
