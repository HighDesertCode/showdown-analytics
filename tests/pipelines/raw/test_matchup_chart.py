from datetime import date
from decimal import Decimal

import pytest

from pipelines import smogon
from pipelines.raw import matchup_chart
from pipelines.raw.common import ReportFormatError

CHART_1630 = smogon.report_files("matchup_chart", date(2026, 9, 1), [])[0]
BORDER = "+--------+--------+--------+"
# A two-type chart in Smogon's layout (real charts have 18 types). Mirror matches are printed as 0.000%.
REPORT = f"""Matchup Chart and Type Ranking (1630-weighted)
{BORDER}
|        |water   |ground  |
{BORDER}
|water   |    2.10|   71.16|
|        |  0.000%| 72.636%|
{BORDER}
|ground  |   26.81|    3.02|
|        | 27.364%|  0.000%|
{BORDER}

Type.....ViabilityScore
water.............3.628
ground............2.412

"""


def test_parse_builds_cells_and_viability():
    chart = matchup_chart.parse(REPORT.encode(), CHART_1630)

    assert chart.cells == [
        ("water", "water", Decimal("2.10"), Decimal("0.000")),
        ("water", "ground", Decimal("71.16"), Decimal("72.636")),
        ("ground", "water", Decimal("26.81"), Decimal("27.364")),
        ("ground", "ground", Decimal("3.02"), Decimal("0.000")),
    ]
    assert chart.viability == [("water", Decimal("3.628")), ("ground", Decimal("2.412"))]


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("(1630-weighted)", "(1760-weighted)", "expected a 1630-weighted chart"),
        ("|        |water   |", "|corner  |water   |", "line 3: expected an empty corner"),
        ("|ground  |   26.81|", "|fire    |   26.81|", "one row per column type"),
        ("   71.16|", "  71.16%|", "line 5"),
        (" 72.636%|", " 72.636 |", "line 6"),
        ("|        | 27.364%|", "|ground  | 27.364%|", "line 9: expected an empty first cell"),
        ("Type.....ViabilityScore", "Type Ranking", "line 12"),
        ("ground............2.412", "fire..............2.412", "ranking of the chart's types"),
    ],
)
def test_parse_rejects_unexpected_shapes(old, new, message):
    with pytest.raises(ReportFormatError, match=message):
        matchup_chart.parse(REPORT.replace(old, new, 1).encode(), CHART_1630)
