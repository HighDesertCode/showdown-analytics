"""PostgreSQL connections for pipelines.

Settings come from libpq's standard PG* environment variables (PGHOST, PGDATABASE, PGUSER, ...),
loaded from .env by `uv run --env-file .env`.
"""

import os

import psycopg

REQUIRED_SETTINGS = ("PGHOST", "PGDATABASE", "PGUSER")


def connect() -> psycopg.Connection:
    missing = [name for name in REQUIRED_SETTINGS if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"Missing database settings: {', '.join(missing)}")
    if os.environ["PGDATABASE"] == "defaultdb":
        raise RuntimeError("Refusing to connect to defaultdb; project data belongs in showdown-database.")
    return psycopg.connect()
