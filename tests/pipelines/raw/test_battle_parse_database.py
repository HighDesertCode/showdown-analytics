"""Runs pipelines.raw.battle against real tables built from sql/ (see tests/conftest.py)."""

from dataclasses import replace
from datetime import UTC, datetime

from pipelines.battle_events import Event
from pipelines.battle_log import Battle, PreviewPokemon, Side
from pipelines.raw import battle, replay
from pipelines.replays import Replay

REPLAY = Replay(
    "gen9monotype-2703725750",
    "gen9monotype",
    "[Gen 9] Monotype",
    ("jago421", "MistyMarill"),
    1113,
    datetime(2026, 10, 24, 4, 54, 59, tzinfo=UTC),
    "|win|jago421\n",
)
BATTLE = Battle(
    replay_id=REPLAY.replay_id,
    rated=True,
    started_at=datetime(2026, 10, 24, 4, 49, 47, tzinfo=UTC),
    ended_at=datetime(2026, 10, 24, 4, 54, 12, tzinfo=UTC),
    turns=15,
    winner="p1",
    ended_by="knockout",
    rules=("Sleep Clause Mod", "Terastal Clause"),
    sides=(Side("p1", "jago421", 1093, 1123, "win"), Side("p2", "MistyMarill", 1141, 1113, "loss")),
    team=(PreviewPokemon("p1", 1, "Gengar", "Gengar"), PreviewPokemon("p2", 1, "Mimikyu", None)),
    events=(
        Event(1, 1, "p1", "Gengar", "move", "Toxic Spikes", "p2", "Tinkaton", log_line="|move|p1a: Gengar|…"),
        Event(2, 1, "p2", None, "side start", "Toxic Spikes", caused_by_seq=1, log_line="|-sidestart|p2: …"),
        Event(
            3,
            2,
            "p2",
            "Clefable",
            "status",
            "psn",
            caused_by_seq=2,
            source="Toxic Spikes",
            source_inferred=True,
            log_line="|-status|p2a: Clefable|psn",
        ),
        Event(4, 2, "p2", "Clefable", "damage", damage_percent=76, hp_after_percent=24, log_line="|-damage|…"),
    ),
)
PARSED_AT = datetime(2026, 11, 1, tzinfo=UTC)


def store(conn, *replays: Replay) -> None:
    for stored in replays:
        replay.insert(conn, stored, PARSED_AT)


def test_insert_stores_the_battle_its_sides_and_team(conn):
    store(conn, REPLAY)

    battle.insert(conn, BATTLE, PARSED_AT)

    assert conn.execute(
        "SELECT rated, started_at, ended_at, turns, winner, ended_by, rules, parsed_at FROM raw.battle"
    ).fetchone() == (True, BATTLE.started_at, BATTLE.ended_at, 15, "p1", "knockout", list(BATTLE.rules), PARSED_AT)
    assert conn.execute(
        "SELECT side, player, elo_before, elo_after, result FROM raw.battle_side ORDER BY side"
    ).fetchall() == [("p1", "jago421", 1093, 1123, "win"), ("p2", "MistyMarill", 1141, 1113, "loss")]
    assert conn.execute(
        "SELECT side, slot, species, nickname FROM raw.battle_pokemon ORDER BY side, slot"
    ).fetchall() == [("p1", 1, "Gengar", "Gengar"), ("p2", 1, "Mimikyu", None)]


def test_unparsed_ids_lists_replays_without_a_battle_oldest_first(conn):
    older = replace(REPLAY, replay_id="gen9monotype-1", uploaded_at=datetime(2026, 3, 1, tzinfo=UTC))
    newest = replace(REPLAY, replay_id="gen9monotype-3", uploaded_at=datetime(2026, 10, 30, tzinfo=UTC))
    store(conn, REPLAY, older, newest)
    battle.insert(conn, BATTLE, PARSED_AT)

    assert battle.unparsed_ids(conn) == ["gen9monotype-1", "gen9monotype-3"]


def test_log_reads_one_replay(conn):
    store(conn, REPLAY)

    assert battle.log(conn, REPLAY.replay_id) == "|win|jago421\n"


def test_insert_stores_the_events(conn):
    store(conn, REPLAY)

    battle.insert(conn, BATTLE, PARSED_AT)

    assert conn.execute(
        "SELECT seq, event, detail, target_pokemon, damage_percent, hp_after_percent, caused_by_seq, source,"
        " source_inferred FROM raw.battle_event ORDER BY seq"
    ).fetchall() == [
        (1, "move", "Toxic Spikes", "Tinkaton", None, None, None, None, False),
        (2, "side start", "Toxic Spikes", None, None, None, 1, None, False),
        (3, "status", "psn", None, None, None, 2, "Toxic Spikes", True),
        (4, "damage", None, None, 76, 24, None, None, False),
    ]


def test_delete_removes_the_whole_parse_and_a_new_one_can_be_inserted(conn):
    store(conn, REPLAY)
    battle.insert(conn, BATTLE, PARSED_AT)

    battle.delete(conn, REPLAY.replay_id)
    battle.insert(conn, replace(BATTLE, turns=16), PARSED_AT)

    assert conn.execute("SELECT turns FROM raw.battle").fetchall() == [(16,)]
    assert conn.execute("SELECT COUNT(*) FROM raw.battle_event").fetchone() == (4,)


def test_all_ids_lists_every_replay_oldest_first(conn):
    older = replace(REPLAY, replay_id="gen9monotype-1", uploaded_at=datetime(2026, 3, 1, tzinfo=UTC))
    store(conn, REPLAY, older)
    battle.insert(conn, BATTLE, PARSED_AT)

    assert battle.all_ids(conn) == ["gen9monotype-1", REPLAY.replay_id]
