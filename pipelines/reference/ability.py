"""Loads reference.ability from Showdown's abilities.js, with descriptions from data/text/abilities.ts."""

from psycopg import Connection

from pipelines.reference.common import insert_new

COLUMNS = ["showdown_id", "name", "num", "short_description", "nonstandard"]


def rows(abilities: dict, ability_text: dict) -> list[tuple]:
    return [
        (
            showdown_id,
            ability["name"],
            ability["num"],
            ability_text.get(showdown_id, {}).get("shortDesc"),
            ability.get("isNonstandard"),
        )
        for showdown_id, ability in abilities.items()
    ]


def load(conn: Connection, abilities: dict, ability_text: dict) -> int:
    return insert_new(conn, "ability", COLUMNS, rows(abilities, ability_text))
