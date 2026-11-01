"""Checks the parsed battle tables' constraints and showdown-analyst's grants on them (see conftest.py)."""

from datetime import UTC, datetime

import psycopg
import pytest

from pipelines.raw import replay
from pipelines.replays import Replay

REPLAY_ID = "gen9monotype-2703725750"
EVENT = (
    "INSERT INTO raw.battle_event (replay_id, seq, turn, side, pokemon, event, caused_by_seq, log_line)"
    " VALUES (%s, %s, 1, 'p1', 'Gengar', %s, %s, %s)"
)


@pytest.fixture
def battle(conn):
    """A stored replay with one parsed battle: a side, a Pokémon, and a move with the hazard it set."""
    replay.insert(
        conn,
        Replay(
            REPLAY_ID,
            "gen9monotype",
            "[Gen 9] Monotype",
            ("jago421", "MistyMarill"),
            1113,
            datetime(2026, 10, 24, 4, 54, 59, tzinfo=UTC),
            "|win|jago421\n",
        ),
        datetime(2026, 10, 31, tzinfo=UTC),
    )
    conn.execute(
        "INSERT INTO raw.battle (replay_id, rated, started_at, ended_at, turns, winner, ended_by, rules, parsed_at)"
        " VALUES (%s, TRUE, '2026-10-24T04:49:47Z', '2026-10-24T04:54:12Z', 15, 'p1', 'knockout', '{}', NOW())",
        (REPLAY_ID,),
    )
    conn.execute(
        "INSERT INTO raw.battle_side (replay_id, side, player, elo_before, elo_after, result)"
        " VALUES (%s, 'p1', 'jago421', 1093, 1123, 'win')",
        (REPLAY_ID,),
    )
    conn.execute(
        "INSERT INTO raw.battle_pokemon (replay_id, side, slot, species, nickname)"
        " VALUES (%s, 'p1', 1, 'Gengar', 'Gengar')",
        (REPLAY_ID,),
    )
    conn.execute(EVENT, (REPLAY_ID, 1, "move", None, "|move|p1a: Gengar|Toxic Spikes|p2a: Tinkaton"))
    conn.execute(EVENT, (REPLAY_ID, 2, "hazard", 1, "|-sidestart|p2: MistyMarill|move: Toxic Spikes"))


def count(conn, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM raw.{table}").fetchone()[0]


def test_deleting_a_battle_deletes_its_parse_but_keeps_the_replay(conn, battle):
    conn.execute("DELETE FROM raw.battle WHERE replay_id = %s", (REPLAY_ID,))

    assert [count(conn, table) for table in ("battle", "battle_side", "battle_pokemon", "battle_event")] == [0] * 4
    assert count(conn, "replay") == 1


def test_analyst_cannot_delete_the_replay_behind_a_battle(conn, battle):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("DELETE FROM raw.replay")


def test_a_battle_needs_its_replay(conn):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        conn.execute(
            "INSERT INTO raw.battle (replay_id, rated, started_at, ended_at, turns, ended_by, rules, parsed_at)"
            " VALUES ('gen9monotype-1', FALSE, NOW(), NOW(), 0, 'tie', '{}', NOW())"
        )


@pytest.mark.parametrize(
    ("caused_by_seq", "error"),
    [(3, psycopg.errors.CheckViolation), (None, None)],
)
def test_an_event_is_caused_only_by_an_earlier_event(conn, battle, caused_by_seq, error):
    values = (REPLAY_ID, 3, "damage", caused_by_seq, "|-damage|p2a: Tinkaton|50/100")
    if error is None:
        conn.execute(EVENT, values)
    else:
        with pytest.raises(error):
            conn.execute(EVENT, values)


def test_an_event_cannot_be_caused_by_a_missing_event(conn, battle):
    # seq 3 doesn't exist yet; the check allows it, the foreign key doesn't.
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        conn.execute(EVENT, (REPLAY_ID, 4, "damage", 3, "|-damage|p2a: Tinkaton|50/100"))
