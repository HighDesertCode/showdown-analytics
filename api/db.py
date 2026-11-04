"""The API's connection pool, and how the endpoints read a page of rows.

Settings come from libpq's standard PG* environment variables, loaded from .env.api by `uv run --env-file .env.api`.
The API connects only as showdown-api, which can read the api schema and nothing else, and only with
PGSSLMODE=verify-full to a database that isn't local.
"""

import os
from collections.abc import Iterator, Sequence
from typing import Annotated, Any, LiteralString

import psycopg
from fastapi import Depends, Request
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from api.responses import Page

REQUIRED_SETTINGS = ("PGHOST", "PGDATABASE", "PGUSER")
LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")
API_ROLE = "showdown-api"
# showdown-api allows 10 connections. Four per instance leaves room for a deployment, when the old and new
# instances run at once.
MAX_CONNECTIONS = 4
# Every pooled connection runs in autocommit mode, so a request's reads don't pay for BEGIN and COMMIT round trips
# (under READ COMMITTED each statement sees its own snapshot either way), and returns rows as dicts.
CONNECTION_KWARGS: dict[str, Any] = {"autocommit": True, "row_factory": dict_row}


def create_pool() -> ConnectionPool:
    """A pool that isn't open yet; the app opens it at startup and closes it at shutdown."""
    missing = [name for name in REQUIRED_SETTINGS if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"Missing database settings: {', '.join(missing)}")
    if os.environ["PGUSER"] != API_ROLE:
        raise RuntimeError(f"Refusing to connect as {os.environ['PGUSER']}; the API connects only as {API_ROLE}.")
    if os.environ["PGHOST"] not in LOCAL_HOSTS and os.environ.get("PGSSLMODE") != "verify-full":
        raise RuntimeError("Refusing to connect without PGSSLMODE=verify-full to a database that isn't local.")
    # An empty conninfo, so libpq reads the PG* variables.
    return ConnectionPool("", min_size=1, max_size=MAX_CONNECTIONS, kwargs=CONNECTION_KWARGS, open=False)


def connection(request: Request) -> Iterator[psycopg.Connection[dict[str, Any]]]:
    """A pooled connection for one request, given back to the pool afterwards."""
    with request.app.state.pool.connection() as conn:
        yield conn


# The parameter type for endpoints that query the database.
Connection = Annotated[psycopg.Connection[dict[str, Any]], Depends(connection)]


def paginate(
    conn: psycopg.Connection[dict[str, Any]],
    columns: LiteralString,
    source: LiteralString,
    where: LiteralString,
    order: LiteralString,
    args: Sequence[Any],
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], Page]:
    """One page of rows from a FROM clause, and the Page with the total matching the filter, in one round trip.

    COUNT(*) OVER () puts the total on every row, so no second query counts it. A page past the end has no rows to
    carry it, so only then is the total counted separately.
    """
    rows = conn.execute(
        f"SELECT {columns}, COUNT(*) OVER () AS total FROM {source} WHERE {where} ORDER BY {order} LIMIT %s OFFSET %s",
        (*args, limit, offset),
    ).fetchall()
    if rows:
        total = rows[0]["total"]
        for row in rows:
            del row["total"]
    elif offset:
        counted = conn.execute(f"SELECT COUNT(*) AS total FROM {source} WHERE {where}", args).fetchone()
        total = counted["total"] if counted else 0
    else:
        total = 0
    return rows, Page(limit=limit, offset=offset, total=total)
