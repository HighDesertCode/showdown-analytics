"""Loads reference.type from Showdown's typechart.js. The Tera-only Stellar type is skipped."""

from psycopg import Connection

from pipelines.reference.common import insert_new

EXCLUDED = {"stellar"}


def rows(typechart: dict) -> list[tuple[str, str]]:
    # Keys are Showdown IDs; every standard type name is the ID capitalized (water -> Water).
    return [(showdown_id, showdown_id.capitalize()) for showdown_id in typechart if showdown_id not in EXCLUDED]


def load(conn: Connection, typechart: dict) -> int:
    return insert_new(conn, "type", ["showdown_id", "name"], rows(typechart))
