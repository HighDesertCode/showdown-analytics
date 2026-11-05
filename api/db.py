"""The API's connection pool, and how the endpoints read a page of rows.

Settings come from libpq's standard PG* environment variables, loaded from .env.api by `uv run --env-file .env.api`.
The API connects only as showdown-api, which can read the api schema and nothing else, and only with
PGSSLMODE=verify-full to a database that isn't local. On App Platform, the attached database supplies its CA
certificate as text in DATABASE_CA_CERT, which the pool writes to a file for libpq.
"""

import atexit
import os
import tempfile
from collections.abc import Iterator, Sequence
from pathlib import Path
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
CONNECTION_KWARGS: dict[str, Any] = {"autocommit": True, "row_factory": dict_row, "connect_timeout": 5}
# connect_timeout (seconds) makes an attempt that gets no answer fail, so the pool logs why ("error connecting in
# 'pool-1': connection timeout expired"). Without it, a firewall that drops packets, such as a database whose trusted
# sources leave the app out, keeps the attempt waiting while every request only answers 503.
# Holds the CA certificate's text where it can't be a file, as in App Platform's environment variables.
CA_CERT_SETTING = "DATABASE_CA_CERT"


def use_ca_cert_from_environment() -> None:
    """Writes the certificate in DATABASE_CA_CERT to a file and points PGSSLROOTCERT at it.

    libpq reads the CA certificate only from a file. Does nothing when DATABASE_CA_CERT isn't set, as locally,
    where .env.api names the file in PGSSLROOTCERT. pipelines.db does the same; the API keeps its own copy so it
    never depends on the ingestion code.
    """
    pem = os.environ.get(CA_CERT_SETTING)
    if not pem:
        return
    if os.environ.get("PGSSLROOTCERT"):
        raise RuntimeError(f"Set {CA_CERT_SETTING} or PGSSLROOTCERT, not both")
    if not pem.lstrip().startswith("-----BEGIN CERTIFICATE-----"):
        raise RuntimeError(f"{CA_CERT_SETTING} doesn't hold a PEM certificate")
    # A new file only this user can read, removed when the API exits.
    fd, path = tempfile.mkstemp(prefix="database-ca-", suffix=".crt")
    with os.fdopen(fd, "w") as file:
        file.write(pem)
    atexit.register(Path(path).unlink, missing_ok=True)
    os.environ["PGSSLROOTCERT"] = path


def create_pool() -> ConnectionPool:
    """A pool that isn't open yet; the app opens it at startup and closes it at shutdown."""
    missing = [name for name in REQUIRED_SETTINGS if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"Missing database settings: {', '.join(missing)}")
    if os.environ["PGUSER"] != API_ROLE:
        raise RuntimeError(f"Refusing to connect as {os.environ['PGUSER']}; the API connects only as {API_ROLE}.")
    if os.environ["PGHOST"] not in LOCAL_HOSTS and os.environ.get("PGSSLMODE") != "verify-full":
        raise RuntimeError("Refusing to connect without PGSSLMODE=verify-full to a database that isn't local.")
    use_ca_cert_from_environment()
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
