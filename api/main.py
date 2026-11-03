"""The FastAPI app. Run it with `uv run --group api --env-file .env.api uvicorn api.main:app`."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI, HTTPException, Request
from psycopg_pool import ConnectionPool

from api.db import create_pool

# How long the health check waits for a connection before reporting the database unavailable.
HEALTH_TIMEOUT_SECONDS = 5


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

    app = FastAPI(title="Showdown Analytics API", lifespan=lifespan)

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
