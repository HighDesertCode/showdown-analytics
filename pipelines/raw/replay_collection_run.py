"""Records each `collect-replays` run in raw.replay_collection_run: its progress after every replay, then its result."""

from datetime import UTC, datetime

from psycopg import Connection, sql

# The counter each replay outcome adds to.
COUNTERS = {"loaded": "replays_loaded", "failed": "replays_failed"}


def start(conn: Connection, format_id: str) -> int:
    """Records a running run and returns its replay_collection_run_id."""
    row = conn.execute(
        "INSERT INTO raw.replay_collection_run (format_id, started_at, status)"
        " VALUES (%s, %s, 'running') RETURNING replay_collection_run_id",
        (format_id, datetime.now(UTC)),
    ).fetchone()
    if row is None:
        raise RuntimeError("Could not record the run")
    return row[0]


def record_replay(conn: Connection, run_id: int, outcome: str) -> None:
    """Adds one replay to the run's loaded or failed count."""
    counter = sql.Identifier(COUNTERS[outcome])
    conn.execute(
        sql.SQL(
            "UPDATE raw.replay_collection_run SET {counter} = {counter} + 1 WHERE replay_collection_run_id = %s"
        ).format(counter=counter),
        (run_id,),
    )


def finish(conn: Connection, run_id: int, status: str, error: str | None = None) -> None:
    """Records the run's result: succeeded, partial (some downloads failed), or failed with its error."""
    conn.execute(
        "UPDATE raw.replay_collection_run SET finished_at = %s, status = %s, error = %s"
        " WHERE replay_collection_run_id = %s",
        (datetime.now(UTC), status, error, run_id),
    )
