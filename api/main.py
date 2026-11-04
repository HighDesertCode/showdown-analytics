"""The FastAPI app. Run it with `uv run --group api --env-file .env.api uvicorn api.main:app`."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from importlib.metadata import version

import psycopg
from fastapi import FastAPI, HTTPException, Request
from fastapi.routing import APIRoute
from psycopg_pool import ConnectionPool

from api import battles, reference, replays, smogon
from api.db import create_pool

# How long the health check waits for a connection before reporting the database unavailable.
HEALTH_TIMEOUT_SECONDS = 5
# What an agent reads first: the sources, why they're never comparable, and the shape every response shares.
DESCRIPTION = (
    "Competitive Pokémon statistics for Gen 9 Monotype, from two sources that are never comparable: Smogon's monthly "
    "usage reports, which cover every rated ladder battle and weight each team by a rating baseline (1630 or 1760), "
    "and public Pokémon Showdown replays, a sample of the battles players chose to upload, grouped by Elo band (1000, "
    "1200, 1400, or 1600 and up). Every response has the same shape: scope says what the data covers and which source "
    "it came from, with every default filled in; sources lists the Smogon files behind it; data holds the rows; page "
    "gives the total for paginated lists. Shares run from 0 to 1 and each field's description names its denominator. "
    "Filters take names as well as Showdown IDs (Ninetales-Alola or ninetalesalola), and the latest month is the "
    "default."
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
        lifespan=lifespan,
    )
    app.include_router(smogon.router)
    app.include_router(replays.router)
    app.include_router(battles.router)
    app.include_router(reference.router)

    @app.get("/health")
    def health(request: Request) -> dict[str, str]:
        """Whether the API is running and can reach the database."""
        try:
            with request.app.state.pool.connection(timeout=HEALTH_TIMEOUT_SECONDS) as conn:
                conn.execute("SELECT 1")
        except psycopg.Error as error:
            raise HTTPException(status_code=503, detail="Database unavailable") from error
        return {"status": "ok"}

    return app


app = create_app()
