"""Stores parsed battles in raw.battle, raw.battle_side, raw.battle_pokemon, and raw.battle_event."""

from datetime import datetime

from psycopg import Connection

from pipelines.battle_log import Battle
from pipelines.raw.common import copy_rows

EVENT_COLUMNS = (
    "replay_id", "seq", "turn", "side", "pokemon", "event", "detail", "target_side", "target_pokemon",
    "damage_percent", "hp_after_percent", "healed_percent", "caused_by_seq", "source", "source_inferred", "log_line",
)  # fmt: skip


def unparsed_ids(conn: Connection) -> list[str]:
    """The stored replays with no parsed battle, oldest upload first."""
    rows = conn.execute(
        "SELECT r.replay_id FROM raw.replay AS r LEFT JOIN raw.battle AS b USING (replay_id)"
        " WHERE b.replay_id IS NULL ORDER BY r.uploaded_at, r.replay_id"
    )
    return [replay_id for (replay_id,) in rows]


def all_ids(conn: Connection) -> list[str]:
    """Every stored replay, oldest upload first, for re-parsing them all."""
    rows = conn.execute("SELECT replay_id FROM raw.replay ORDER BY uploaded_at, replay_id")
    return [replay_id for (replay_id,) in rows]


def delete(conn: Connection, replay_id: str) -> None:
    """Deletes a battle's parse; its sides, Pokémon, and events go with it (ON DELETE CASCADE)."""
    conn.execute("DELETE FROM raw.battle WHERE replay_id = %s", (replay_id,))


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
    copy_rows(
        conn,
        "battle_event",
        list(EVENT_COLUMNS),
        [(battle.replay_id, *(getattr(event, column) for column in EVENT_COLUMNS[1:])) for event in battle.events],
    )
