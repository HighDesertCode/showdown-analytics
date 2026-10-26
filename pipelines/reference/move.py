"""Loads reference.move and reference.move_effect from Showdown's moves.json, with descriptions from data/text/moves.ts.

Each move yields up to three kinds of effects, numbered in this order: its top-level guaranteed
effect, its `self` effect on the user, and each chance-based secondary effect.
"""

from psycopg import Connection

from pipelines.reference.common import existing_ids, insert, insert_new
from pipelines.showdown import to_id

COLUMNS = [
    "showdown_id",
    "name",
    "num",
    "type_id",
    "category",
    "base_power",
    "accuracy",
    "pp",
    "priority",
    "target",
    "short_description",
    "nonstandard",
]
EFFECT_COLUMNS = [
    "move_id",
    "effect_number",
    "is_secondary",
    "chance",
    "affects",
    "status",
    "volatile_status",
    "field_effect",
    "atk_stages",
    "def_stages",
    "spa_stages",
    "spd_stages",
    "spe_stages",
    "accuracy_stages",
    "evasion_stages",
]
BOOST_STATS = ("atk", "def", "spa", "spd", "spe", "accuracy", "evasion")
WHOLE_FIELD_KEYS = ("weather", "terrain", "pseudoWeather")
SIDE_KEYS = ("sideCondition", "slotCondition")
# Move targets meaning the user or its own side; anything else is the move's target.
SELF_TARGETS = {"self", "allySide", "allyTeam"}


def rows(moves: dict, move_text: dict, type_ids: dict[str, int]) -> list[tuple]:
    return [
        (
            showdown_id,
            move["name"],
            move["num"],
            type_ids[to_id(move["type"])],
            move["category"],
            move["basePower"],
            None if move["accuracy"] is True else move["accuracy"],
            move["pp"],
            move["priority"],
            move["target"],
            move_text.get(showdown_id, {}).get("shortDesc"),
            move.get("isNonstandard"),
        )
        for showdown_id, move in moves.items()
    ]


def effect_details(source: dict) -> tuple:
    """Returns (status, volatile_status, field_effect, *stat stages) from a move, its `self`, or a secondary."""
    field_key = next((key for key in WHOLE_FIELD_KEYS + SIDE_KEYS if key in source), None)
    boosts = source.get("boosts", {})
    return (
        source.get("status"),
        source.get("volatileStatus"),
        to_id(source[field_key]) if field_key else None,
        *(boosts.get(stat) for stat in BOOST_STATS),
    )


def affects(source: dict, default: str) -> str:
    return "field" if any(key in source for key in WHOLE_FIELD_KEYS) else default


def effects(move: dict) -> list[tuple]:
    """Returns (is_secondary, chance, affects, *effect_details) for each effect of a move."""
    found = []

    details = effect_details(move)
    if any(value is not None for value in details):
        default = "self" if move["target"] in SELF_TARGETS else "target"
        found.append((False, 100, affects(move, default), *details))

    if self_effect := move.get("self"):
        details = effect_details(self_effect)
        if any(value is not None for value in details):
            chance = self_effect.get("chance")  # Only Diamond Storm's self effect has a chance.
            found.append((chance is not None, chance or 100, affects(self_effect, "self"), *details))

    secondaries = move.get("secondaries") or ([move["secondary"]] if move.get("secondary") else [])
    for secondary in secondaries:
        # Secondaries with only a chance (e.g. Tri Attack) are implemented in code; see short_description.
        if "self" in secondary:
            found.append((True, secondary["chance"], "self", *effect_details(secondary["self"])))
        else:
            found.append((True, secondary["chance"], "target", *effect_details(secondary)))

    return found


def effect_rows(moves: dict, move_ids: dict[str, int]) -> list[tuple]:
    return [
        (move_ids[showdown_id], effect_number, *effect)
        for showdown_id, move in moves.items()
        for effect_number, effect in enumerate(effects(move), start=1)
    ]


def load(conn: Connection, moves: dict, move_text: dict) -> tuple[int, int]:
    """Returns (moves inserted, move_effect rows inserted). Requires types loaded first."""
    new_move_ids = insert_new(conn, "move", COLUMNS, rows(moves, move_text, existing_ids(conn, "type")))

    # Effects are written only together with their new move, so a reload never mixes an existing
    # move's effects with a changed version from Showdown.
    new_moves = {showdown_id: move for showdown_id, move in moves.items() if showdown_id in new_move_ids}
    new_effects = effect_rows(new_moves, existing_ids(conn, "move"))
    insert(conn, "move_effect", EFFECT_COLUMNS, new_effects)
    return len(new_move_ids), len(new_effects)
