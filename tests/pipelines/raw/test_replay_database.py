"""Runs pipelines.raw.replay against real tables built from sql/ (see tests/pipelines/conftest.py)."""

from dataclasses import replace
from datetime import UTC, datetime

import psycopg
import pytest

from pipelines.raw import replay
from pipelines.replays import Replay

REPLAY = Replay(
    replay_id="gen9monotype-2703725750",
    format_id="gen9monotype",
    format="[Gen 9] Monotype",
    players=("jago421", "MistyMarill"),
    rating=1113,
    uploaded_at=datetime(2026, 10, 24, 4, 54, 59, tzinfo=UTC),
    log="|j|☆jago421\n|win|jago421\n",
)
RETRIEVED_AT = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)


def test_insert_stores_the_replay(conn):
    replay.insert(conn, REPLAY, RETRIEVED_AT)

    assert conn.execute(
        "SELECT replay_id, format_id, format, players, rating, uploaded_at, log, retrieved_at FROM raw.replay"
    ).fetchone() == (
        "gen9monotype-2703725750",
        "gen9monotype",
        "[Gen 9] Monotype",
        ["jago421", "MistyMarill"],
        1113,
        REPLAY.uploaded_at,
        REPLAY.log,
        RETRIEVED_AT,
    )


def test_insert_stores_an_unrated_replay(conn):
    replay.insert(conn, replace(REPLAY, rating=None), RETRIEVED_AT)

    assert conn.execute("SELECT rating FROM raw.replay").fetchone() == (None,)


def test_a_replay_is_stored_once(conn):
    replay.insert(conn, REPLAY, RETRIEVED_AT)

    with pytest.raises(psycopg.errors.UniqueViolation):
        replay.insert(conn, REPLAY, RETRIEVED_AT)


def test_newest_upload(conn):
    assert replay.newest_upload(conn, "gen9monotype") is None

    replay.insert(conn, REPLAY, RETRIEVED_AT)
    replay.insert(
        conn, replace(REPLAY, replay_id="gen9monotype-1", uploaded_at=datetime(2026, 3, 1, tzinfo=UTC)), RETRIEVED_AT
    )
    replay.insert(
        conn, replace(REPLAY, replay_id="gen9ou-1", format_id="gen9ou", uploaded_at=RETRIEVED_AT), RETRIEVED_AT
    )

    assert replay.newest_upload(conn, "gen9monotype") == REPLAY.uploaded_at


def test_stored_ids(conn):
    replay.insert(conn, REPLAY, RETRIEVED_AT)

    assert replay.stored_ids(conn, ["gen9monotype-2703725750", "gen9monotype-1"]) == {"gen9monotype-2703725750"}


@pytest.mark.parametrize(
    "statement",
    ["UPDATE raw.replay SET rating = 0", "DELETE FROM raw.replay"],
)
def test_analyst_cannot_change_or_delete_a_replay(conn, statement):
    replay.insert(conn, REPLAY, RETRIEVED_AT)

    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(statement)
