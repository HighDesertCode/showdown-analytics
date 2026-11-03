"""Query parameters the endpoints share, and how their values are read."""

import re
from datetime import date
from typing import Annotated

from fastapi import HTTPException, Query

DEFAULT_FORMAT = "gen9monotype"
# REPORT.md recommends 1630 as the default view; the baseline is always echoed in the scope.
DEFAULT_BASELINE = 1630
MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"

Format = Annotated[str, Query(description="The Showdown format.")]
Month = Annotated[
    str | None,
    Query(pattern=MONTH_PATTERN, description="The reporting month, as YYYY-MM. Defaults to the latest month."),
]
Baseline = Annotated[
    int,
    Query(description="The rating baseline teams are weighted by. 1630 reflects good players, 1760 strong players."),
]
TeamType = Annotated[
    str | None,
    Query(description="A team type, e.g. water or Water, for teams of that type only. Leave out for all teams."),
]
Limit = Annotated[int, Query(ge=1, le=500, description="The most rows to return.")]
Offset = Annotated[int, Query(ge=0, description="Rows to skip, for the next page.")]


def to_id(name: str) -> str:
    """Showdown's ID for a name: lowercase letters and digits only, so Ninetales-Alola becomes ninetalesalola."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def parse_month(month: str) -> date:
    year, number = month.split("-")
    return date(int(year), int(number), 1)


def format_month(month: date) -> str:
    return month.strftime("%Y-%m")


def team_type_id(team_type: str | None) -> str | None:
    """The team type's Showdown ID, or None for all teams (left out, or "overall")."""
    if team_type is None or to_id(team_type) == "overall":
        return None
    return type_id(team_type)


Type = Annotated[str | None, Query(description="A type, e.g. water or Water. Leave out for every type.")]


def type_id(type_name: str | None) -> str | None:
    """A type's Showdown ID, or None when left out."""
    if type_name is None:
        return None
    showdown_id = to_id(type_name)
    if not showdown_id:
        raise HTTPException(status_code=422, detail=f"{type_name!r} isn't a type")
    return showdown_id
