"""Stores parsed battles in raw.battle, raw.battle_side, and raw.battle_pokemon."""

from datetime import datetime

from psycopg import Connection

from pipelines.battle_log import Battle
from pipelines.raw.common import copy_rows


def unparsed_ids(conn: Connection) -> list[str]:
    """The stored replays with no parsed battle, oldest upload first."""
    rows = conn.execute(
        "SELECT r.replay_id FROM raw.replay AS r LEFT JOIN raw.battle AS b USING (replay_id)"
        " WHERE b.replay_id IS NULL ORDER BY r.uploaded_at, r.replay_id"
    )
    return [replay_id for (replay_id,) in rows]


def log(conn: Connection, replay_id: str) -> str:
    """One replay's log, read on its own so a large backlog is never held in memory at once."""
    row = conn.execute("SELECT log FROM raw.replay WHERE replay_id = %s", (replay_id,)).fetchone()
    if row is None:
        raise LookupError(f"{replay_id} isn't stored")
    return row[0]


def insert(conn: Connection, battle: Battle, parsed_at: datetime) -> None:
    conn.execute(
        "INSERT INTO raw.battle (replay_id, rated, started_at, ended_at, turns, winner, ended_by, rules, parsed_at)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (
            battle.replay_id,
            battle.rated,
            battle.started_at,
            battle.ended_at,
            battle.turns,
            battle.winner,
            battle.ended_by,
            list(battle.rules),
            parsed_at,
        ),
    )
    copy_rows(
        conn,
        "battle_side",
        ["replay_id", "side", "player", "elo_before", "elo_after", "result"],
        [(battle.replay_id, s.side, s.player, s.elo_before, s.elo_after, s.result) for s in battle.sides],
    )
    copy_rows(
        conn,
        "battle_pokemon",
        ["replay_id", "side", "slot", "species", "nickname"],
        [(battle.replay_id, p.side, p.slot, p.species, p.nickname) for p in battle.team],
    )
