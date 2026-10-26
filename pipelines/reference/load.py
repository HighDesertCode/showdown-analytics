"""Loads every reference table in foreign-key order."""

from psycopg import Connection

from pipelines.reference import ability, item, move, nature, species
from pipelines.reference import type as type_loader


def load_all(conn: Connection, sources: dict[str, dict]) -> dict[str, int]:
    """Returns the rows inserted per table."""
    counts = {
        "type": type_loader.load(conn, sources["types"]),
        "ability": ability.load(conn, sources["abilities"], sources["ability_text"]),
    }
    counts["species"], counts["species_ability"] = species.load(conn, sources["species"])
    counts["move"], counts["move_effect"] = move.load(conn, sources["moves"], sources["move_text"])
    counts["item"] = item.load(conn, sources["items"], sources["item_text"])
    counts["nature"] = nature.load(conn, sources["natures"])
    return counts
