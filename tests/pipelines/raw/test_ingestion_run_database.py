"""Checks raw.ingestion_run's constraints and showdown-analyst's grants on it (see tests/pipelines/conftest.py)."""

from datetime import date

import psycopg
import pytest

from pipelines.raw import ingestion_run

START = "INSERT INTO raw.ingestion_run (report_month, families, started_at, status) VALUES (%s, %s, %s, %s)"


def start_run(conn) -> int:
    row = conn.execute(START + " RETURNING ingestion_run_id", ("2026-09-01", ["chaos"], "2026-10-01T12:00Z", "running"))
    return row.fetchone()[0]


def test_analyst_updates_progress_and_result(conn):
    run_id = start_run(conn)

    conn.execute("UPDATE raw.ingestion_run SET files_loaded = files_loaded + 1 WHERE ingestion_run_id = %s", (run_id,))
    conn.execute(
        "UPDATE raw.ingestion_run SET status = 'failed', finished_at = '2026-10-01T12:05Z', error = 'boom'"
        " WHERE ingestion_run_id = %s",
        (run_id,),
    )

    assert conn.execute(
        "SELECT status, files_loaded, error FROM raw.ingestion_run WHERE ingestion_run_id = %s", (run_id,)
    ).fetchone() == ("failed", 1, "boom")


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE raw.ingestion_run SET started_at = '2026-10-02T12:00Z'",
        "UPDATE raw.ingestion_run SET report_month = '2026-08-01'",
        "DELETE FROM raw.ingestion_run",
    ],
)
def test_analyst_cannot_rewrite_or_delete_a_run(conn, statement):
    start_run(conn)

    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(statement)


@pytest.mark.parametrize(
    ("status", "finished_at", "error", "constraint"),
    [
        ("running", "2026-10-01T12:05Z", None, "ingestion_run_finished"),
        ("succeeded", None, None, "ingestion_run_finished"),
        ("failed", "2026-10-01T12:05Z", None, "ingestion_run_error"),
        ("partial", "2026-10-01T12:05Z", "boom", "ingestion_run_error"),
    ],
)
def test_status_matches_finished_at_and_error(conn, status, finished_at, error, constraint):
    with pytest.raises(psycopg.errors.CheckViolation, match=constraint):
        conn.execute(
            "INSERT INTO raw.ingestion_run (report_month, families, started_at, finished_at, status, error)"
            " VALUES ('2026-09-01', '{chaos}', '2026-10-01T12:00Z', %s, %s, %s)",
            (finished_at, status, error),
        )


def test_a_run_records_its_progress_and_result(conn):
    run_id = ingestion_run.start(conn, date(2026, 9, 1), ["chaos", "usage"])
    for outcome in ["loaded", "loaded", "skipped", "failed"]:
        ingestion_run.record_file(conn, run_id, outcome)
    ingestion_run.finish(conn, run_id, "partial")

    assert conn.execute(
        "SELECT report_month, families, status, files_loaded, files_skipped, files_failed, error,"
        " finished_at >= started_at FROM raw.ingestion_run WHERE ingestion_run_id = %s",
        (run_id,),
    ).fetchone() == (date(2026, 9, 1), ["chaos", "usage"], "partial", 2, 1, 1, None, True)


def test_a_failed_run_records_its_error(conn):
    run_id = ingestion_run.start(conn, date(2026, 9, 1), ["chaos"])
    ingestion_run.finish(conn, run_id, "failed", "ReportFormatError: unexpected header")

    assert conn.execute(
        "SELECT status, error FROM raw.ingestion_run WHERE ingestion_run_id = %s", (run_id,)
    ).fetchone() == ("failed", "ReportFormatError: unexpected header")
