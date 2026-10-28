"""Helpers shared by the raw loaders."""

from typing import Protocol

from psycopg import Connection, sql


class ReportFormatError(ValueError):
    """A Smogon file does not have the shape its parser expects."""


class Report(Protocol):
    """A parsed report, ready to insert under its source_file row."""

    def load(self, conn: Connection, source_file_id: int) -> dict[str, int]: ...


def copy_rows(conn: Connection, table: str, columns: list[str], rows: list[tuple]) -> None:
    """Streams rows into a raw table with COPY, which is far faster than one INSERT per row."""
    query = sql.SQL("COPY raw.{table} ({columns}) FROM STDIN").format(
        table=sql.Identifier(table),
        columns=sql.SQL(", ").join(map(sql.Identifier, columns)),
    )
    with conn.cursor() as cursor, cursor.copy(query) as copy:
        for row in rows:
            copy.write_row(row)
