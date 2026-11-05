"""The FastAPI app. Run it with `uv run --group api --env-file .env.api uvicorn api.main:app`."""

import hmac
import os
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from importlib.metadata import version

import psycopg
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.routing import APIRoute
from psycopg_pool import ConnectionPool

from api import battles, reference, replays, smogon
from api.db import create_pool
from api.responses import SERVICE_UNAVAILABLE

# How long the health check waits for a connection before reporting the database unavailable.
HEALTH_TIMEOUT_SECONDS = 5
# What a 503 tells the client, and how long it suggests waiting before trying again.
RETRY_AFTER_SECONDS = 5
QUERY_TIMEOUT_DETAIL = "The query took too long; try again shortly, with a smaller limit or a narrower filter."
UNAVAILABLE_DETAIL = "Database unavailable; try again shortly."
# Cloudflare sits in front of the API: it rate limits clients and caches responses for as long as Cache-Control
# allows. The data changes only after the daily builds, so a successful answer is reusable for ten minutes.
CACHE_SECONDS = 600
# Cloudflare adds this header, holding the secret in ORIGIN_SECRET, to every request it forwards, so a request
# without it skipped Cloudflare's rate limits by calling the app's own address. Unset (as locally), nothing is checked.
ORIGIN_SECRET_SETTING = "ORIGIN_SECRET"
ORIGIN_HEADER = "X-Origin-Secret"
# App Platform's health checks reach the app directly, not through Cloudflare, and need a live answer every time.
HEALTH_PATH = "/health"
FORBIDDEN_DETAIL = "Call the API through its public address."
# What an agent reads first: the sources, why they're never comparable, and the shape every response shares.
DESCRIPTION = (
    "Competitive Pokémon statistics for Gen 9 Monotype, from two sources that are never comparable: Smogon's monthly "
    "usage reports, which cover every rated ladder battle and weight each team by a rating baseline (1630 or 1760), "
    "and public Pokémon Showdown replays, a sample of the battles players chose to upload, grouped by Elo band (1000, "
    "1200, 1400, or 1600 and up). Every response has the same shape: scope says what the data covers and which source "
    "it came from, with every default filled in; sources lists the Smogon files behind it; data holds the rows; page "
    "gives the total for paginated lists. Shares run from 0 to 1 and each field's description names its denominator. "
    "Filters take names as well as Showdown IDs (Ninetales-Alola or ninetalesalola), and the latest month is the "
    "default (for replay statistics, the latest complete month)."
)
TAGS = [
    {
        "name": "Smogon statistics",
        "description": "Smogon's monthly usage statistics: ladder-wide, weighted by rating baseline, and scoped by "
        "team type.",
    },
    {
        "name": "Replay statistics",
        "description": "Statistics from public replays, a sample of uploaded battles, by month and Elo band; never "
        "comparable to Smogon's.",
    },
    {"name": "Battles", "description": "Individual public replays: search them, and follow one turn by turn."},
    {
        "name": "Reference data",
        "description": "Pokémon Showdown's species, types, abilities, items, moves, and natures.",
    },
]


def operation_id(route: APIRoute) -> str:
    """The operation's name in the OpenAPI schema, which agents use as a tool name: the endpoint's group and function,
    e.g. smogon_usage or battles_events."""
    if not route.path.startswith("/v1/"):
        return route.name
    return f"{route.path.split('/')[2]}_{route.name}"


def create_app(pool: ConnectionPool | None = None) -> FastAPI:
    """The app, using the given pool (tests pass their own) or one built from the environment."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        app.state.pool = pool or create_pool()
        app.state.pool.open()
        try:
            yield
        finally:
            app.state.pool.close()

    app = FastAPI(
        title="Showdown Analytics API",
        # The project's version from pyproject.toml; its major version is the /v1 prefix.
        version=version("showdown-analytics"),
        description=DESCRIPTION,
        openapi_tags=TAGS,
        generate_unique_id_function=operation_id,
        responses=SERVICE_UNAVAILABLE,
        lifespan=lifespan,
    )
    app.include_router(smogon.router)
    app.include_router(replays.router)
    app.include_router(battles.router)
    app.include_router(reference.router)

    origin_secret = os.environ.get(ORIGIN_SECRET_SETTING, "")

    @app.middleware("http")
    async def edge(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """Refuses requests that didn't come through Cloudflare, and tells Cloudflare which answers it may cache:
        only successful GETs of the data under /v1, never an error, a 503, or the health check."""
        if origin_secret and request.url.path != HEALTH_PATH:
            sent = request.headers.get(ORIGIN_HEADER, "")
            if not hmac.compare_digest(sent.encode(), origin_secret.encode()):
                return JSONResponse(
                    status_code=403, content={"detail": FORBIDDEN_DETAIL}, headers={"Cache-Control": "no-store"}
                )
        response = await call_next(request)
        cacheable = request.method == "GET" and response.status_code == 200 and request.url.path.startswith("/v1/")
        response.headers["Cache-Control"] = f"public, max-age={CACHE_SECONDS}" if cacheable else "no-store"
        return response

    @app.get(HEALTH_PATH)
    def health(request: Request) -> dict[str, str]:
        """Whether the API is running and can reach the database; a 503 when it can't."""
        with request.app.state.pool.connection(timeout=HEALTH_TIMEOUT_SECONDS) as conn:
            conn.execute("SELECT 1")
        return {"status": "ok"}

    @app.exception_handler(psycopg.OperationalError)
    def database_unavailable(request: Request, error: psycopg.OperationalError) -> JSONResponse:
        """A 503 when the database can't answer: no free connection, a lost one, or a query past the statement
        timeout, which psycopg raises as QueryCanceled."""
        timed_out = isinstance(error, psycopg.errors.QueryCanceled)
        return JSONResponse(
            status_code=503,
            content={"detail": QUERY_TIMEOUT_DETAIL if timed_out else UNAVAILABLE_DETAIL},
            headers={"Retry-After": str(RETRY_AFTER_SECONDS)},
        )

    return app


app = create_app()
