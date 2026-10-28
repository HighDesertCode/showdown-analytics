"""Validates Smogon's metagame text reports and turns them into rows for the raw.metagame_* tables.

A report lists tags with dot leaders, a blank line, then a stalliness histogram:

    monotype..........100.00000%
    stall.............52.49034%

    Stalliness (mean: 1.730)
        |#
    -1.0|##
    ...
    more negative = more offensive, more positive = more stall
    one # = 0.63%

Only the tags and the stalliness mean are stored. The histogram is a rounded drawing, so its bars are
validated (to catch format changes) but not stored.
"""

import re
from dataclasses import dataclass
from decimal import Decimal

from psycopg import Connection

from pipelines.raw.common import ReportFormatError, copy_rows
from pipelines.raw.text_table import match

TAG = re.compile(r"([a-z0-9]+)\.+(\d+\.\d+)%")
STALLINESS_MEAN = re.compile(r"Stalliness \(mean: (-?\d+\.\d+)\)")
HISTOGRAM_BAR = re.compile(r"( {4}|[ +-]\d+\.\d)\|#*")
LEGEND = re.compile(r"more negative = more offensive, more positive = more stall")
SCALE = re.compile(r"one # = \d+\.\d+%")


@dataclass(frozen=True)
class MetagameReport:
    stalliness_mean: Decimal
    tags: list[tuple]  # tag, percent

    def load(self, conn: Connection, source_file_id: int) -> dict[str, int]:
        """Inserts a parsed report under an existing source_file row; returns the rows inserted per table."""
        conn.execute(
            "INSERT INTO raw.metagame_report (source_file_id, stalliness_mean) VALUES (%s, %s)",
            (source_file_id, self.stalliness_mean),
        )
        copy_rows(conn, "metagame_tag", ["source_file_id", "tag", "percent"], [(source_file_id, *t) for t in self.tags])
        return {"tags": len(self.tags)}


def parse(content: bytes) -> MetagameReport:
    lines = content.decode("utf-8").splitlines()
    if "" not in lines:
        raise ReportFormatError("expected a blank line between the tags and the stalliness histogram")
    blank = lines.index("")
    if len(lines) < blank + 4:
        raise ReportFormatError(f"expected a stalliness histogram after line {blank + 1}")

    tags = []
    for number, line in enumerate(lines[:blank], start=1):
        tag = match(TAG, line, number)
        tags.append((tag.group(1), Decimal(tag.group(2))))

    stalliness_mean = Decimal(match(STALLINESS_MEAN, lines[blank + 1], blank + 2).group(1))
    for number, line in enumerate(lines[blank + 2 : -2], start=blank + 3):
        match(HISTOGRAM_BAR, line, number)
    match(LEGEND, lines[-2], len(lines) - 1)
    match(SCALE, lines[-1], len(lines))
    return MetagameReport(stalliness_mean, tags)
