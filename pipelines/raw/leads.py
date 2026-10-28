"""Validates Smogon's leads text reports and turns them into rows for the raw.leads_* tables.

A report is one header line followed by a table (see text_table):

    Total leads: 127144
    + ---- + ------------------ + --------- + ------ + ------- +
    | Rank | Pokemon            | Usage %   | Raw    | %       |
    ...
"""

import re
from dataclasses import dataclass

from psycopg import Connection

from pipelines.raw import text_table
from pipelines.raw.common import ReportFormatError, copy_rows

COLUMNS = ["Rank", "Pokemon", "Usage %", "Raw", "%"]
TOTAL_LEADS = re.compile(r"Total leads: (\d+)")


@dataclass(frozen=True)
class LeadsReport:
    lead_count: int
    pokemon: list[tuple]  # rank, pokemon, usage_percent, raw_count, raw_percent

    def load(self, conn: Connection, source_file_id: int) -> dict[str, int]:
        """Inserts a parsed report under an existing source_file row; returns the rows inserted per table."""
        conn.execute(
            "INSERT INTO raw.leads_report (source_file_id, lead_count) VALUES (%s, %s)",
            (source_file_id, self.lead_count),
        )
        copy_rows(
            conn,
            "leads_pokemon",
            ["source_file_id", "rank", "pokemon", "usage_percent", "raw_count", "raw_percent"],
            [(source_file_id, *row) for row in self.pokemon],
        )
        return {"pokemon": len(self.pokemon)}


def parse(content: bytes) -> LeadsReport:
    lines = content.decode("utf-8").splitlines()
    if not lines:
        raise ReportFormatError("expected a header line, got an empty file")
    lead_count = int(text_table.match(TOTAL_LEADS, lines[0], 1).group(1))
    pokemon = [
        (
            text_table.integer(rank, number),
            name,
            text_table.percent(usage, number),
            text_table.integer(raw, number),
            text_table.percent(raw_percent, number),
        )
        for number, (rank, name, usage, raw, raw_percent) in text_table.rows(lines, 1, COLUMNS)
    ]
    return LeadsReport(lead_count, pokemon)
