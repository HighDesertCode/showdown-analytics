"""Validates Smogon's usage text reports and turns them into rows for the raw.usage_* tables.

A report is two header lines and a bordered table:

    Total battles: 63572
    Avg. weight/team: 0.192
    + ---- + ------------------ + --------- + ------ + ------- + ------ + ------- +
    | Rank | Pokemon            | Usage %   | Raw    | %       | Real   | %       |
    + ---- + ------------------ + --------- + ------ + ------- + ------ + ------- +
    | 1    | Dragapult          | 15.95180% | 15179  | 11.938% | 11396  | 11.603% |
    + ---- + ------------------ + --------- + ------ + ------- + ------ + ------- +

Long names can push a row out of alignment, so rows are split on "|" rather than read by position.
"""

import re
from dataclasses import dataclass
from decimal import Decimal

from psycopg import Connection

from pipelines.raw.common import ReportFormatError, copy_rows

HEADER = ["Rank", "Pokemon", "Usage %", "Raw", "%", "Real", "%"]
BORDER = re.compile(r"\+( -+ \+)+")
TOTAL_BATTLES = re.compile(r"Total battles: (\d+)")
AVG_TEAM_WEIGHT = re.compile(r"Avg\. weight/team: (\d+\.\d+)")
INTEGER = re.compile(r"\d+")
PERCENT = re.compile(r"(\d+\.\d+)%")


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
    if len(lines) < 6:
        raise ReportFormatError(f"expected at least 6 lines, got {len(lines)}")
    battle_count = int(match(TOTAL_BATTLES, lines[0], 1).group(1))
    avg_team_weight = Decimal(match(AVG_TEAM_WEIGHT, lines[1], 2).group(1))
    for number in (3, 5, len(lines)):
        match(BORDER, lines[number - 1], number)
    if cells(lines[3], 4) != HEADER:
        raise ReportFormatError(f"line 4: expected columns {HEADER}, got {cells(lines[3], 4)}")

    pokemon = []
    for number, line in enumerate(lines[5:-1], start=6):
        rank, name, usage, raw, raw_percent, real, real_percent = cells(line, number)
        pokemon.append(
            (
                int(match(INTEGER, rank, number).group()),
                name,
                Decimal(match(PERCENT, usage, number).group(1)),
                int(match(INTEGER, raw, number).group()),
                Decimal(match(PERCENT, raw_percent, number).group(1)),
                int(match(INTEGER, real, number).group()),
                Decimal(match(PERCENT, real_percent, number).group(1)),
            )
        )
    return UsageReport((battle_count, avg_team_weight), pokemon)


def cells(line: str, number: int) -> list[str]:
    """Splits a "| a | b |" table row into its seven stripped cells."""
    if not (line.startswith("|") and line.endswith("|")):
        raise ReportFormatError(f"line {number}: expected a table row, got {line!r}")
    values = [cell.strip() for cell in line[1:-1].split("|")]
    if len(values) != len(HEADER):
        raise ReportFormatError(f"line {number}: expected {len(HEADER)} cells, got {len(values)}")
    return values


def match(pattern: re.Pattern[str], text: str, number: int) -> re.Match[str]:
    """Matches the whole text against the pattern, or raises an error naming the line."""
    result = pattern.fullmatch(text)
    if result is None:
        raise ReportFormatError(f"line {number}: expected {pattern.pattern!r}, got {text!r}")
    return result
