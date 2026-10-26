"""Helpers shared by the reference loaders."""

from psycopg import Connection, sql


def existing_ids(conn: Connection, table: str) -> dict[str, int]:
    """Maps each showdown_id in a reference table to its primary key, e.g. {"water": 1}."""
    query = sql.SQL("SELECT showdown_id, {id} FROM reference.{table}").format(
        id=sql.Identifier(f"{table}_id"),
        table=sql.Identifier(table),
    )
    return dict(conn.execute(query).fetchall())


def insert(conn: Connection, table: str, columns: list[str], rows: list[tuple]) -> None:
    query = sql.SQL("INSERT INTO reference.{table} ({columns}) VALUES ({values})").format(
        table=sql.Identifier(table),
        columns=sql.SQL(", ").join(map(sql.Identifier, columns)),
        values=sql.SQL(", ").join([sql.Placeholder()] * len(columns)),
    )
    with conn.cursor() as cursor:
        cursor.executemany(query, rows)


def insert_new(conn: Connection, table: str, columns: list[str], rows: list[tuple]) -> set[str]:
    """Inserts rows whose showdown_id (the first column) is not already in the table; returns the inserted IDs.

    Existing rows are skipped up front instead of using ON CONFLICT DO NOTHING, which would use up
    an identity value for every skipped row.
    """
    if columns[0] != "showdown_id":
        raise ValueError("The first column must be showdown_id")
    existing = existing_ids(conn, table)
    new_rows = [row for row in rows if row[0] not in existing]
    insert(conn, table, columns, new_rows)
    return {row[0] for row in new_rows}
