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


@dataclass(frozen=True)
class Family:
    """Where a report family's files live within a month's folder."""

    overall: str  # Path of the overall report.
    team_type: str | None  # Path of each per-type report, or None if the family has none.


FAMILIES = {
    "chaos": Family("chaos/{format}-{baseline}.json", "monotype/chaos/{format}-mono{team_type}-{baseline}.json"),
    "usage": Family("{format}-{baseline}.txt", "monotype/{format}-mono{team_type}-{baseline}.txt"),
    "leads": Family("leads/{format}-{baseline}.txt", "monotype/leads/{format}-mono{team_type}-{baseline}.txt"),
    "metagame": Family("metagame/{format}-{baseline}.txt", "monotype/metagame/{format}-mono{team_type}-{baseline}.txt"),
    # One chart covers every type pairing, so there are no per-type charts.
    "matchup_chart": Family("monotype/matchupcharts/{format}-matchup_chart-{baseline}.txt", None),
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
    paths = FAMILIES[family]
    path = paths.overall if team_type is None else paths.team_type
    if path is None:
        raise ValueError(f"{family} has no per-type reports")
    return f"{STATS_URL}/{month:%Y-%m}/" + path.format(format=format, baseline=baseline, team_type=team_type)


def report_files(
    family: str, month: date, team_types: list[str], format: str = FORMAT, baselines: tuple[int, ...] = BASELINES
) -> list[ReportFile]:
    """Lists one family's files for a month: the overall report plus one per team type, at each baseline."""
    scopes = [None, *team_types] if FAMILIES[family].team_type else [None]
    return [
        ReportFile(family, format, month, baseline, team_type, url(family, month, baseline, team_type, format))
        for baseline in baselines
        for team_type in scopes
    ]
