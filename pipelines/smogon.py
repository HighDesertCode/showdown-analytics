"""Builds the URLs of Smogon's monthly usage statistics files.

Smogon publishes static files, one folder per month, at https://www.smogon.com/stats/. Each report
covers either all teams (overall) or, in Monotype, the teams of one type (e.g. "monowater").
"""

import re
from dataclasses import dataclass
from datetime import date

STATS_URL = "https://www.smogon.com/stats"
FORMAT = "gen9monotype"
BASELINES = (1630, 1760)

# Each family's directory and file extension within a month's folder.
FAMILIES = {
    "chaos": ("chaos/", "json"),
}


@dataclass(frozen=True)
class ReportFile:
    family: str
    format: str
    report_month: date
    baseline: int
    team_type: str | None  # A type's showdown_id (e.g. "water"), or None for the overall report.
    url: str


def parse_month(text: str) -> date:
    """Parses "2026-09" into the first day of that month."""
    if not re.fullmatch(r"\d{4}-\d{2}", text):
        raise ValueError(f"Expected a month like 2026-09, got {text!r}")
    return date.fromisoformat(f"{text}-01")


def url(family: str, month: date, baseline: int, team_type: str | None = None, format: str = FORMAT) -> str:
    directory, extension = FAMILIES[family]
    if team_type is None:
        path = f"{directory}{format}-{baseline}.{extension}"
    else:
        path = f"monotype/{directory}{format}-mono{team_type}-{baseline}.{extension}"
    return f"{STATS_URL}/{month:%Y-%m}/{path}"


def report_files(
    family: str, month: date, team_types: list[str], format: str = FORMAT, baselines: tuple[int, ...] = BASELINES
) -> list[ReportFile]:
    """Lists one family's files for a month: the overall report plus one per team type, at each baseline."""
    return [
        ReportFile(family, format, month, baseline, team_type, url(family, month, baseline, team_type, format))
        for baseline in baselines
        for team_type in [None, *team_types]
    ]
