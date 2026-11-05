"""Query parameters the endpoints share, and how their values are read."""

import re
from datetime import UTC, date, datetime
from enum import IntEnum
from typing import Annotated

from fastapi import HTTPException, Query

DEFAULT_FORMAT = "gen9monotype"
# REPORT.md recommends 1630 as the default view; the baseline is always echoed in the scope.
DEFAULT_BASELINE = 1630
# Years 2000 to 2099: every month the data could cover, and none the date helpers can't represent (year 0, or a
# battle search in 9999-12, whose end would fall in year 10000).
MONTH_PATTERN = r"^20\d{2}-(0[1-9]|1[0-2])$"


class Band(IntEnum):
    """Showdown Elo bands, by their lower bound."""

    floor = 1000
    elo_1200 = 1200
    elo_1400 = 1400
    elo_1600 = 1600


Format = Annotated[str, Query(description="The Showdown format.")]
Month = Annotated[
    str | None,
    Query(pattern=MONTH_PATTERN, description="The reporting month, as YYYY-MM. Defaults to the latest month."),
]
ReplayMonth = Annotated[
    str | None,
    Query(
        pattern=MONTH_PATTERN,
        description=(
            "The UTC month the battles started, as YYYY-MM. Defaults to the latest complete month, so the numbers"
            " don't shift while you read them; ask for the current month to get its partial counts."
        ),
    ),
]
BattleMonth = Annotated[
    str | None,
    Query(
        pattern=MONTH_PATTERN,
        description="Only battles that started in this UTC month, as YYYY-MM. Leave out for every month.",
    ),
]
Baseline = Annotated[
    int,
    Query(
        description="The rating baseline teams are weighted by, not a rating cutoff: every rated battle counts, and "
        "higher-rated players' teams count more. 1630 reflects good players, 1760 strong players."
    ),
]
TeamType = Annotated[
    str | None,
    Query(
        description=(
            "A team type, e.g. water or Water, for teams of that type only: Smogon's per-type report, or replay teams "
            "whose six previewed Pokémon share that type. Leave out, or pass overall, for all teams."
        )
    ),
]
Type = Annotated[str | None, Query(description="A type, e.g. water or Water. Leave out for every type.")]
EloBand = Annotated[
    Band | None,
    Query(
        description=(
            "Only this Elo band: the lower bound of the player's Showdown Elo before the battle (1000 is the ladder's "
            "floor, up to 1199; 1600 means 1600 and up). Leave out for every band."
        )
    ),
]
Limit = Annotated[int, Query(ge=1, le=500, description="The most rows to return.")]
Offset = Annotated[int, Query(ge=0, description="Rows to skip, for the next page.")]


def to_id(name: str) -> str:
    """Showdown's ID for a name: lowercase letters and digits only, so Ninetales-Alola becomes ninetalesalola."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def showdown_id(name: str, what: str) -> str:
    """The Showdown ID of a name a client sent; a 422 naming what was expected when no letters or digits are left."""
    result = to_id(name)
    if not result:
        raise HTTPException(status_code=422, detail=f"{name!r} isn't a {what}")
    return result


def optional_id(name: str | None, what: str) -> str | None:
    """showdown_id for a filter that may be left out."""
    return showdown_id(name, what) if name is not None else None


def type_id(name: str | None) -> str | None:
    """A type filter's Showdown ID, or None for every type: left out, or overall."""
    result = optional_id(name, "type")
    return None if result == "overall" else result


def parse_month(month: str) -> date:
    year, number = month.split("-")
    return date(int(year), int(number), 1)


def format_month(month: date) -> str:
    return month.strftime("%Y-%m")


def month_bounds(month: date) -> tuple[datetime, datetime]:
    """The instants a month starts and ends at: midnight UTC on its first day, and on the next month's."""
    start = datetime(month.year, month.month, 1, tzinfo=UTC)
    end = datetime(month.year + month.month // 12, month.month % 12 + 1, 1, tzinfo=UTC)
    return start, end


def current_month() -> date:
    """The first day of the month in progress, in UTC, the time zone replays are grouped by."""
    return datetime.now(UTC).date().replace(day=1)
