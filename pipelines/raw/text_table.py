"""Parses the bordered text tables in Smogon's usage and leads reports:

    + ---- + ------------------ + --------- +
    | Rank | Pokemon            | Usage %   |
    + ---- + ------------------ + --------- +
    | 1    | Dragapult          | 15.95180% |
    + ---- + ------------------ + --------- +

Long names can push a row out of alignment, so rows are split on "|" rather than read by position.
Line numbers in errors count from 1, as in a text editor.
"""

import re
from decimal import Decimal

from pipelines.raw.common import ReportFormatError

BORDER = re.compile(r"\+( -+ \+)+")
INTEGER = re.compile(r"\d+")
PERCENT = re.compile(r"(\d+\.\d+)%")


def rows(lines: list[str], start: int, columns: list[str]) -> list[tuple[int, list[str]]]:
    """Validates a table that begins at lines[start] and runs to the last line.

    Returns each row's line number and cells.
    """
    if len(lines) < start + 4:
        raise ReportFormatError(f"expected a table starting on line {start + 1}, got {len(lines)} lines")
    for index in (start, start + 2, len(lines) - 1):
        match(BORDER, lines[index], index + 1)
    header = cells(lines[start + 1], start + 2, len(columns))
    if header != columns:
        raise ReportFormatError(f"line {start + 2}: expected columns {columns}, got {header}")
    return [
        (number, cells(line, number, len(columns)))
        for number, line in enumerate(lines[start + 3 : -1], start=start + 4)
    ]


def cells(line: str, number: int, count: int) -> list[str]:
    """Splits a "| a | b |" row into its stripped cells."""
    if not (line.startswith("|") and line.endswith("|")):
        raise ReportFormatError(f"line {number}: expected a table row, got {line!r}")
    values = [cell.strip() for cell in line[1:-1].split("|")]
    if len(values) != count:
        raise ReportFormatError(f"line {number}: expected {count} cells, got {len(values)}")
    return values


def match(pattern: re.Pattern[str], text: str, number: int) -> re.Match[str]:
    """Matches the whole text against the pattern, or raises an error naming the line."""
    result = pattern.fullmatch(text)
    if result is None:
        raise ReportFormatError(f"line {number}: expected {pattern.pattern!r}, got {text!r}")
    return result


def integer(text: str, number: int) -> int:
    return int(match(INTEGER, text, number).group())


def percent(text: str, number: int) -> Decimal:
    """Parses "15.95180%" as Decimal("15.95180"), keeping the printed precision."""
    return Decimal(match(PERCENT, text, number).group(1))
