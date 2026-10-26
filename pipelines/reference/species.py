"""Loads reference.species and reference.species_ability from Showdown's pokedex.json.

Skipped: cosmetic forms (they share their base form's data), `Custom` entries such as MissingNo.
and Pokéstar Studios props, and special-event abilities (slot "S").
"""

from psycopg import Connection

from pipelines.reference.common import existing_ids, insert_new
from pipelines.showdown import to_id

COLUMNS = [
    "showdown_id", "name", "dex_number", "base_species", "forme", "type_1_id", "type_2_id",
    "hp", "atk", "def", "spa", "spd", "spe", "nonstandard",
]
STATS = ("hp", "atk", "def", "spa", "spd", "spe")
ABILITY_SLOTS = ("0", "1", "H")


def is_included(entry: dict) -> bool:
    return not entry.get("isCosmeticForme") and entry.get("isNonstandard") != "Custom"


def rows(pokedex: dict, type_ids: dict[str, int]) -> list[tuple]:
    result = []
    for showdown_id, entry in pokedex.items():
        if not is_included(entry):
            continue
        entry_type_ids = [type_ids[to_id(name)] for name in entry["types"]]
        type_2_id = entry_type_ids[1] if len(entry_type_ids) > 1 else None
        stats = [entry["baseStats"][stat] for stat in STATS]
        result.append((
            showdown_id, entry["name"], entry["num"], entry.get("baseSpecies"), entry.get("forme"),
            entry_type_ids[0], type_2_id, *stats, entry.get("isNonstandard"),
        ))
    return result


def ability_rows(pokedex: dict, species_ids: dict[str, int], ability_ids: dict[str, int]) -> list[tuple]:
    return [
        (species_ids[showdown_id], slot, ability_ids[to_id(ability_name)])
        for showdown_id, entry in pokedex.items()
        if is_included(entry)
        for slot, ability_name in entry["abilities"].items()
        if slot in ABILITY_SLOTS
    ]


def load(conn: Connection, pokedex: dict) -> tuple[int, int]:
    """Returns (species inserted, species_ability links inserted). Requires types and abilities loaded first."""
    species_count = insert_new(conn, "species", COLUMNS, rows(pokedex, existing_ids(conn, "type")))

    links = ability_rows(pokedex, existing_ids(conn, "species"), existing_ids(conn, "ability"))
    existing_links = set(conn.execute("SELECT species_id, slot FROM reference.species_ability").fetchall())
    new_links = [link for link in links if link[:2] not in existing_links]
    with conn.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO reference.species_ability (species_id, slot, ability_id) VALUES (%s, %s, %s)",
            new_links,
        )
    return species_count, len(new_links)
