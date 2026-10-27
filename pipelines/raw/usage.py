"""Validates Smogon's usage text reports and turns them into rows for the raw.usage_* tables.

A report is two header lines followed by a table (see text_table):

    Total battles: 63572
    Avg. weight/team: 0.192
    + ---- + ------------------ + --------- + ------ + ------- + ------ + ------- +
    | Rank | Pokemon            | Usage %   | Raw    | %       | Real   | %       |
    ...
"""

import re
from dataclasses import dataclass
from decimal import Decimal

from psycopg import Connection

from pipelines.raw import text_table
from pipelines.raw.common import ReportFormatError, copy_rows

COLUMNS = ["Rank", "Pokemon", "Usage %", "Raw", "%", "Real", "%"]
TOTAL_BATTLES = re.compile(r"Total battles: (\d+)")
AVG_TEAM_WEIGHT = re.compile(r"Avg\. weight/team: (\d+\.\d+)")


@dataclass(frozen=True)
class UsageReport:
    info: tuple  # battle_count, avg_team_weight
    pokemon: list[tuple]  # rank, pokemon, usage_percent, raw_count, raw_percent, real_count, real_percent

    def load(self, conn: Connection, source_file_id: int) -> dict[str, int]:
        """Inserts a parsed report under an existing source_file row; returns the rows inserted per table."""
        conn.execute(
            "INSERT INTO raw.usage_report (source_file_id, battle_count, avg_team_weight) VALUES (%s, %s, %s)",
            (source_file_id, *self.info),
        )
        copy_rows(
            conn,
            "usage_pokemon",
            ["source_file_id", "rank", "pokemon", "usage_percent", "raw_count", "raw_percent"]
            + ["real_count", "real_percent"],
            [(source_file_id, *row) for row in self.pokemon],
        )
        return {"pokemon": len(self.pokemon)}


def parse(content: bytes) -> UsageReport:
    lines = content.decode("utf-8").splitlines()
    if len(lines) < 2:
        raise ReportFormatError(f"expected header lines, got {len(lines)} lines")
    battle_count = int(text_table.match(TOTAL_BATTLES, lines[0], 1).group(1))
    avg_team_weight = Decimal(text_table.match(AVG_TEAM_WEIGHT, lines[1], 2).group(1))
    pokemon = [
        (
            text_table.integer(rank, number),
            name,
            text_table.percent(usage, number),
            text_table.integer(raw, number),
            text_table.percent(raw_percent, number),
            text_table.integer(real, number),
            text_table.percent(real_percent, number),
        )
        for number, (rank, name, usage, raw, raw_percent, real, real_percent) in text_table.rows(lines, 2, COLUMNS)
    ]
    return UsageReport((battle_count, avg_team_weight), pokemon)
