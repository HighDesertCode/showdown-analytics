"""Stores public replays in raw.replay, once each, as published."""

from datetime import datetime

from psycopg import Connection

from pipelines.replays import Replay


def newest_upload(conn: Connection, format_id: str) -> datetime | None:
    """The upload time of the newest stored replay in the format, where a run with no window resumes."""
    row = conn.execute("SELECT MAX(uploaded_at) FROM raw.replay WHERE format_id = %s", (format_id,)).fetchone()
    return None if row is None else row[0]


def stored_ids(conn: Connection, replay_ids: list[str]) -> set[str]:
    """Returns the given replay IDs that are already stored."""
    rows = conn.execute("SELECT replay_id FROM raw.replay WHERE replay_id = ANY(%s)", (replay_ids,))
    return {replay_id for (replay_id,) in rows}


def insert(conn: Connection, replay: Replay, retrieved_at: datetime) -> None:
    conn.execute(
        "INSERT INTO raw.replay (replay_id, format_id, format, players, rating, uploaded_at, log, retrieved_at)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (
            replay.replay_id,
            replay.format_id,
            replay.format,
            list(replay.players),
            replay.rating,
            replay.uploaded_at,
            replay.log,
            retrieved_at,
        ),
    )
