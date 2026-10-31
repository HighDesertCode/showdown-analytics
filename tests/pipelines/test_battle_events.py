import pytest

from pipelines import battle_events, battle_log
from pipelines.battle_events import Event
from pipelines.replays import ReplayFormatError

REPLAY_ID = "gen9monotype-2703725750"
TEAM = {("p1", "Ghostly"): "Gengar", ("p1", "Chandelure"): "Chandelure", ("p2", "Tinkaton"): "Tinkaton",
        ("p2", "Clefable"): "Clefable", ("p2", "Pawmot"): "Pawmot"}  # fmt: skip
OPENING = """|switch|p1a: Ghostly|Gengar, M|100/100
|switch|p2a: Tinkaton|Tinkaton, F|100/100
|turn|1
"""


def parse(log: str) -> tuple[Event, ...]:
    return battle_events.parse(log.splitlines(), TEAM, REPLAY_ID, battle_log.EVENT_TYPES)


def rows(events, *fields):
    return [tuple(getattr(event, field) for field in fields) for event in events]


def test_effects_link_to_their_move_until_the_turn_ends():
    events = parse(
        OPENING
        + """|move|p1a: Ghostly|Shadow Ball|p2a: Tinkaton
|-supereffective|p2a: Tinkaton
|-damage|p2a: Tinkaton|40/100
|-damage|p1a: Ghostly|90/100|[from] item: Life Orb
|
|-heal|p2a: Tinkaton|46/100|[from] item: Leftovers
|upkeep
"""
    )

    assert rows(events[2:], "seq", "turn", "event", "target_pokemon", "damage_percent", "hp_after_percent",
                "healed_percent", "caused_by_seq", "source") == [
        (3, 1, "move", "Tinkaton", None, None, None, None, None),
        (4, 1, "super effective", None, None, None, None, 3, None),
        (5, 1, "damage", None, 60, 40, None, 3, None),
        (6, 1, "damage", None, 10, 90, None, 3, "item: Life Orb"),
        (7, 1, "heal", None, None, 46, 6, None, "item: Leftovers"),
    ]  # fmt: skip
    assert events[0] == Event(1, 0, "p1", "Gengar", "switch", detail="Gengar", hp_after_percent=100,
                              log_line="|switch|p1a: Ghostly|Gengar, M|100/100")  # fmt: skip


def test_hazards_link_to_the_move_that_set_them():
    events = parse(
        OPENING
        + """|move|p1a: Ghostly|Toxic Spikes|p2a: Tinkaton
|-sidestart|p2: MistyMarill|move: Toxic Spikes
|move|p2a: Tinkaton|Stealth Rock|p1a: Ghostly
|-sidestart|p1: jago421|move: Stealth Rock
|move|p1a: Ghostly|Shadow Ball|p2a: Tinkaton
|-damage|p2a: Tinkaton|0 fnt
|faint|p2a: Tinkaton
|
|upkeep
|switch|p2a: Clefable|Clefable, F|100/100
|-status|p2a: Clefable|psn
|turn|2
|switch|p1a: Chandelure|Chandelure, F|100/100
|-damage|p1a: Chandelure|88/100|[from] Stealth Rock
"""
    )

    assert rows(events[2:], "seq", "side", "pokemon", "event", "detail", "caused_by_seq", "source",
                "source_inferred") == [
        (3, "p1", "Gengar", "move", "Toxic Spikes", None, None, False),
        (4, "p2", None, "side start", "Toxic Spikes", 3, None, False),
        (5, "p2", "Tinkaton", "move", "Stealth Rock", None, None, False),
        (6, "p1", None, "side start", "Stealth Rock", 5, None, False),
        (7, "p1", "Gengar", "move", "Shadow Ball", None, None, False),
        (8, "p2", "Tinkaton", "damage", None, 7, None, False),
        (9, "p2", "Tinkaton", "faint", None, 7, None, False),
        (10, "p2", "Clefable", "switch", "Clefable", None, None, False),
        (11, "p2", "Clefable", "status", "psn", 4, "Toxic Spikes", True),
        (12, "p1", "Chandelure", "switch", "Chandelure", None, None, False),
        (13, "p1", "Chandelure", "damage", None, 6, "Stealth Rock", False),
    ]  # fmt: skip


def test_poison_is_not_put_down_to_toxic_spikes_once_the_turn_moves_on():
    events = parse(
        OPENING
        + """|move|p1a: Ghostly|Toxic Spikes|p2a: Tinkaton
|-sidestart|p2: MistyMarill|move: Toxic Spikes
|move|p2a: Tinkaton|Rest|p2a: Tinkaton
|
|-status|p2a: Tinkaton|psn
"""
    )

    assert rows(events[-1:], "caused_by_seq", "source", "source_inferred") == [(None, None, False)]


def test_a_cleared_or_swapped_hazard_is_no_longer_its_sides():
    events = parse(
        OPENING
        + """|move|p1a: Ghostly|Toxic Spikes|p2a: Tinkaton
|-sidestart|p2: MistyMarill|move: Toxic Spikes
|-swapsideconditions
|
|switch|p2a: Clefable|Clefable, F|100/100
|-status|p2a: Clefable|psn
"""
    )

    assert rows(events[-1:], "caused_by_seq", "source_inferred") == [(None, False)]


def test_a_fainted_pokemon_can_be_revived():
    # Destiny Bond faints a Pokémon without a damage line; Revival Blessing then heals it from zero.
    events = parse(
        OPENING
        + """|faint|p2a: Tinkaton
|
|switch|p2a: Pawmot|Pawmot, M|100/100
|turn|2
|move|p2a: Pawmot|Revival Blessing|p2a: Pawmot
|-heal|p2: Tinkaton|50/100|[from] move: Revival Blessing
"""
    )

    assert rows(events[-1:], "event", "healed_percent", "hp_after_percent", "caused_by_seq") == [("heal", 50, 50, 5)]


def test_a_damage_line_that_changes_nothing_is_kept():
    events = parse(OPENING + "|move|p2a: Tinkaton|Play Rough|p1a: Ghostly\n|-damage|p1a: Ghostly|100/100\n")

    assert rows(events[-1:], "event", "damage_percent", "hp_after_percent") == [("damage", None, 100)]


@pytest.mark.parametrize(
    ("line", "detail"),
    [
        ("|-boost|p1a: Ghostly|spa|2", "+2 spa"),
        ("|-unboost|p1a: Ghostly|spa|1", "-1 spa"),
        ("|-setboost|p1a: Ghostly|atk|6|[from] move: Belly Drum", "=6 atk"),
        ("|-start|p1a: Ghostly|typechange|Bug|[from] ability: Protean", "typechange Bug"),
        ("|-enditem|p1a: Ghostly|Leftovers|[from] move: Knock Off|[of] p2a: Tinkaton", "Leftovers"),
    ],
)
def test_details(line, detail):
    assert parse(OPENING + line + "\n")[-1].detail == detail


def test_weather_and_field_events_have_no_pokemon():
    events = parse(
        OPENING
        + """|-weather|Sandstorm|[from] ability: Sand Stream|[of] p2a: Tinkaton
|-weather|Sandstorm|[upkeep]
|-weather|none
|-fieldstart|move: Trick Room|[of] p1a: Ghostly
"""
    )

    assert rows(events[2:], "side", "pokemon", "event", "detail", "target_pokemon", "source") == [
        (None, None, "weather", "Sandstorm", None, "ability: Sand Stream (p2 Tinkaton)"),
        (None, None, "weather continues", "Sandstorm", None, None),
        (None, None, "weather ended", None, None, None),
        (None, None, "field start", "Trick Room", "Gengar", None),
    ]


@pytest.mark.parametrize(
    ("lines", "message"),
    [
        ("|move|p1a: Stranger|Tackle|p2a: Tinkaton", "unknown Pokémon 'p1a: Stranger'"),
        ("|-damage|p1a: Chandelure|50/100", "changes HP before entering"),
        ("|-damage|p1a: Ghostly|50/100\n|-damage|p1a: Ghostly|60/100", "-damage takes p1 Gengar from 50 to 60"),
        ("|-heal|p1a: Ghostly|50/100", "-heal takes p1 Gengar from 100 to 50"),
        ("|-damage|p1a: Ghostly|150/300", "unexpected HP '150/300'"),
    ],
)
def test_parse_rejects_events_that_dont_add_up(lines, message):
    with pytest.raises(ReplayFormatError, match=message):
        parse(OPENING + lines + "\n")
