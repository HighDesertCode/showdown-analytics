"""Loads reference.nature from Showdown's data/natures.ts. Neutral natures have no plus/minus stat."""

from psycopg import Connection

from pipelines.reference.common import insert_new

COLUMNS = ["showdown_id", "name", "increased_stat", "decreased_stat"]


def rows(natures: dict) -> list[tuple]:
    return [
        (showdown_id, nature["name"], nature.get("plus"), nature.get("minus"))
        for showdown_id, nature in natures.items()
    ]


def load(conn: Connection, natures: dict) -> int:
    return len(insert_new(conn, "nature", COLUMNS, rows(natures)))
