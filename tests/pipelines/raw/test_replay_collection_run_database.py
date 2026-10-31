"""Checks raw.replay_collection_run's constraints and showdown-analyst's grants on it (see conftest.py)."""

import psycopg
import pytest

from pipelines.raw import replay_collection_run

START = "INSERT INTO raw.replay_collection_run (format_id, started_at, status) VALUES (%s, %s, %s)"


def start_run(conn) -> int:
    row = conn.execute(START + " RETURNING replay_collection_run_id", ("gen9monotype", "2026-11-01T12:00Z", "running"))
    return row.fetchone()[0]


def test_analyst_updates_progress_and_result(conn):
    run_id = start_run(conn)

    conn.execute(
        "UPDATE raw.replay_collection_run SET replays_loaded = replays_loaded + 1 WHERE replay_collection_run_id = %s",
        (run_id,),
    )
    conn.execute(
        "UPDATE raw.replay_collection_run SET status = 'failed', finished_at = '2026-11-01T12:05Z', error = 'boom'"
        " WHERE replay_collection_run_id = %s",
        (run_id,),
    )

    assert conn.execute(
        "SELECT status, replays_loaded, error FROM raw.replay_collection_run WHERE replay_collection_run_id = %s",
        (run_id,),
    ).fetchone() == ("failed", 1, "boom")


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE raw.replay_collection_run SET started_at = '2026-11-02T12:00Z'",
        "UPDATE raw.replay_collection_run SET format_id = 'gen9ou'",
        "DELETE FROM raw.replay_collection_run",
    ],
)
def test_analyst_cannot_rewrite_or_delete_a_run(conn, statement):
    start_run(conn)

    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(statement)


@pytest.mark.parametrize(
    ("status", "finished_at", "error", "constraint"),
    [
        ("running", "2026-11-01T12:05Z", None, "replay_collection_run_finished"),
        ("succeeded", None, None, "replay_collection_run_finished"),
        ("failed", "2026-11-01T12:05Z", None, "replay_collection_run_error"),
        ("partial", "2026-11-01T12:05Z", "boom", "replay_collection_run_error"),
    ],
)
def test_status_matches_finished_at_and_error(conn, status, finished_at, error, constraint):
    with pytest.raises(psycopg.errors.CheckViolation, match=constraint):
        conn.execute(
            "INSERT INTO raw.replay_collection_run (format_id, started_at, finished_at, status, error)"
            " VALUES ('gen9monotype', '2026-11-01T12:00Z', %s, %s, %s)",
            (finished_at, status, error),
        )


def test_a_run_records_its_progress_and_result(conn):
    run_id = replay_collection_run.start(conn, "gen9monotype")
    for outcome in ["loaded", "loaded", "failed"]:
        replay_collection_run.record_replay(conn, run_id, outcome)
    replay_collection_run.finish(conn, run_id, "partial")

    assert conn.execute(
        "SELECT format_id, status, replays_loaded, replays_failed, error, finished_at >= started_at"
        " FROM raw.replay_collection_run WHERE replay_collection_run_id = %s",
        (run_id,),
    ).fetchone() == ("gen9monotype", "partial", 2, 1, None, True)


def test_a_failed_run_records_its_error(conn):
    run_id = replay_collection_run.start(conn, "gen9monotype")
    replay_collection_run.finish(conn, run_id, "failed", "HTTPError: HTTP Error 503")

    assert conn.execute(
        "SELECT status, error FROM raw.replay_collection_run WHERE replay_collection_run_id = %s", (run_id,)
    ).fetchone() == ("failed", "HTTPError: HTTP Error 503")
