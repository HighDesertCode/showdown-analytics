"""Loads reference.item from Showdown's items.js, with descriptions from data/text/items.ts."""

from psycopg import Connection

from pipelines.reference.common import insert_new

COLUMNS = ["showdown_id", "name", "num", "is_berry", "short_description", "nonstandard"]


def rows(items: dict, item_text: dict) -> list[tuple]:
    return [
        (
            showdown_id,
            item["name"],
            item["num"],
            item.get("isBerry", False),
            item_text.get(showdown_id, {}).get("shortDesc"),
            item.get("isNonstandard"),
        )
        for showdown_id, item in items.items()
    ]


def load(conn: Connection, items: dict, item_text: dict) -> int:
    return insert_new(conn, "item", COLUMNS, rows(items, item_text))
