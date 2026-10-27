"""Validates Smogon's Monotype matchup charts and turns them into rows for the raw.matchup_chart_* tables.

A chart is a title, a grid with two lines per type, and a type ranking:

    Matchup Chart and Type Ranking (1630-weighted)
    +--------+--------+--------+--
    |        |normal  |fighting| …
    +--------+--------+--------+--
    |normal  |    1.35|    9.43| …     weighted wins of the row type against each column type
    |        |  0.000%| 45.061%| …     the row type's win percent against each column type
    +--------+--------+--------+--
    …

    Type.....ViabilityScore
    bug...............4.053
    …
"""

import re
from dataclasses import dataclass
from decimal import Decimal

from psycopg import Connection

from pipelines.raw.common import ReportFormatError, copy_rows
from pipelines.raw.text_table import cells, match
from pipelines.smogon import ReportFile

TITLE = re.compile(r"Matchup Chart and Type Ranking \((\d+)-weighted\)")
BORDER = re.compile(r"\+(-+\+)+")
TYPE = re.compile(r"[a-z]+")
WINS = re.compile(r"\d+\.\d+")
PERCENT = re.compile(r"(\d+\.\d+)%")
RANKING_HEADER = re.compile(r"Type\.+ViabilityScore")
RANKING = re.compile(r"([a-z]+)\.+(-?\d+\.\d+)")


@dataclass(frozen=True)
class MatchupChart:
    cells: list[tuple]  # type, opponent_type, wins, win_percent
    viability: list[tuple]  # type, viability_score

    def load(self, conn: Connection, source_file_id: int) -> dict[str, int]:
        """Inserts a parsed chart under an existing source_file row; returns the rows inserted per table."""
        conn.execute("INSERT INTO raw.matchup_chart_report (source_file_id) VALUES (%s)", (source_file_id,))
        copy_rows(
            conn,
            "matchup_chart_cell",
            ["source_file_id", "type", "opponent_type", "wins", "win_percent"],
            [(source_file_id, *row) for row in self.cells],
        )
        copy_rows(
            conn,
            "matchup_chart_viability",
            ["source_file_id", "type", "viability_score"],
            [(source_file_id, *row) for row in self.viability],
        )
        return {"cells": len(self.cells), "types": len(self.viability)}


def parse(content: bytes, file: ReportFile) -> MatchupChart:
    # Trailing blank lines are not part of the chart.
    lines = content.decode("utf-8").rstrip("\n").splitlines()
    if not lines:
        raise ReportFormatError("expected a title line, got an empty file")
    baseline = int(match(TITLE, lines[0], 1).group(1))
    if baseline != file.baseline:
        raise ReportFormatError(f"line 1: expected a {file.baseline}-weighted chart, got {baseline}-weighted")
    if len(lines) < 4:
        raise ReportFormatError(f"expected a column header, got {len(lines)} lines")

    # The header row is an empty corner cell followed by one column per type.
    columns = lines[2].count("|") - 1
    corner, *types = cells(lines[2], 3, columns)
    if corner or len(set(types)) != len(types):
        raise ReportFormatError(f"line 3: expected an empty corner and distinct types, got {[corner, *types]}")
    for type_name in types:
        match(TYPE, type_name, 3)
    match(BORDER, lines[1], 2)
    match(BORDER, lines[3], 4)

    grid_end = 4 + 3 * len(types)
    if len(lines) < grid_end + 2 + len(types):
        raise ReportFormatError(f"expected {len(types)} types in the grid and the ranking, got {len(lines)} lines")
    chart, row_types = [], []
    for start in range(4, grid_end, 3):
        row_type, *wins = cells(lines[start], start + 1, columns)
        blank, *percents = cells(lines[start + 1], start + 2, columns)
        if blank:
            raise ReportFormatError(f"line {start + 2}: expected an empty first cell, got {blank!r}")
        match(BORDER, lines[start + 2], start + 3)
        row_types.append(row_type)
        for opponent_type, win, percent in zip(types, wins, percents, strict=True):
            chart.append(
                (
                    row_type,
                    opponent_type,
                    Decimal(match(WINS, win, start + 1).group()),
                    Decimal(match(PERCENT, percent, start + 2).group(1)),
                )
            )
    if sorted(row_types) != sorted(types):
        raise ReportFormatError(f"expected one row per column type, got rows {row_types}")

    if lines[grid_end] != "":
        raise ReportFormatError(f"line {grid_end + 1}: expected a blank line, got {lines[grid_end]!r}")
    match(RANKING_HEADER, lines[grid_end + 1], grid_end + 2)
    viability = []
    for number, line in enumerate(lines[grid_end + 2 :], start=grid_end + 3):
        ranking = match(RANKING, line, number)
        viability.append((ranking.group(1), Decimal(ranking.group(2))))
    if sorted(type_name for type_name, _ in viability) != sorted(types):
        raise ReportFormatError(f"expected a ranking of the chart's types, got {[t for t, _ in viability]}")
    return MatchupChart(chart, viability)
