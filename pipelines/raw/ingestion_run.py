"""Records each `load-smogon` run in raw.ingestion_run: its progress after every file, then its result."""

from datetime import UTC, date, datetime

from psycopg import Connection, sql

# The counter each file outcome adds to.
COUNTERS = {"loaded": "files_loaded", "skipped": "files_skipped", "failed": "files_failed"}


def start(conn: Connection, month: date, families: list[str]) -> int:
    """Records a running run and returns its ingestion_run_id."""
    row = conn.execute(
        "INSERT INTO raw.ingestion_run (report_month, families, started_at, status)"
        " VALUES (%s, %s, %s, 'running') RETURNING ingestion_run_id",
        (month, families, datetime.now(UTC)),
    ).fetchone()
    if row is None:
        raise RuntimeError("Could not record the run")
    return row[0]


def record_file(conn: Connection, run_id: int, outcome: str) -> None:
    """Adds one file to the run's loaded, skipped, or failed count."""
    counter = sql.Identifier(COUNTERS[outcome])
    conn.execute(
        sql.SQL("UPDATE raw.ingestion_run SET {counter} = {counter} + 1 WHERE ingestion_run_id = %s").format(
            counter=counter
        ),
        (run_id,),
    )


def finish(conn: Connection, run_id: int, status: str, error: str | None = None) -> None:
    """Records the run's result: succeeded, partial (some downloads failed), or failed with its error."""
    conn.execute(
        "UPDATE raw.ingestion_run SET finished_at = %s, status = %s, error = %s WHERE ingestion_run_id = %s",
        (datetime.now(UTC), status, error, run_id),
    )
