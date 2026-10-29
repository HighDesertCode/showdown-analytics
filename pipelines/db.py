"""PostgreSQL connections for pipelines.

Settings come from libpq's standard PG* environment variables (PGHOST, PGDATABASE, PGUSER, ...),
loaded from .env by `uv run --env-file .env`. Connections to any database that isn't local require
PGSSLMODE=verify-full, so the server's certificate and hostname are always checked; libpq's default doesn't.
"""

import os

import psycopg

REQUIRED_SETTINGS = ("PGHOST", "PGDATABASE", "PGUSER")
LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")


def connect() -> psycopg.Connection:
    missing = [name for name in REQUIRED_SETTINGS if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"Missing database settings: {', '.join(missing)}")
    if os.environ["PGDATABASE"] == "defaultdb":
        raise RuntimeError("Refusing to connect to defaultdb; project data belongs in showdown-database.")
    if os.environ["PGHOST"] not in LOCAL_HOSTS and os.environ.get("PGSSLMODE") != "verify-full":
        raise RuntimeError("Refusing to connect without PGSSLMODE=verify-full to a database that isn't local.")
    return psycopg.connect()
