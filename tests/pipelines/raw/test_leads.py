from decimal import Decimal

import pytest

from pipelines.raw import leads
from pipelines.raw.common import ReportFormatError

BORDER = "+ ---- + ------------------ + --------- + ------ + ------- +"
# A trimmed real report.
REPORT = f"""Total leads: 127144
{BORDER}
| Rank | Pokemon            | Usage %   | Raw    | %       |
{BORDER}
| 1    | Sneasler           |  3.79446% | 2404   |  1.891% |
| 2    | Ting-Lu            |  3.48046% | 2354   |  1.851% |
{BORDER}
"""


def test_parse_builds_rows():
    report = leads.parse(REPORT.encode())

    assert report.lead_count == 127144
    assert report.pokemon == [
        (1, "Sneasler", Decimal("3.79446"), 2404, Decimal("1.891")),
        (2, "Ting-Lu", Decimal("3.48046"), 2354, Decimal("1.851")),
    ]


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("Total leads: 127144", "Total battles: 63572", "line 1"),
        ("| Raw    | %       |", "| Raw    | Real    |", "line 3: expected columns"),
        ("| 2404   |", "| 2404   | 1 |", "line 5: expected 5 cells"),
        ("1.851%", "1.851", "line 6"),
    ],
)
def test_parse_rejects_unexpected_shapes(old, new, message):
    with pytest.raises(ReportFormatError, match=message):
        leads.parse(REPORT.replace(old, new, 1).encode())


def test_parse_rejects_empty_file():
    with pytest.raises(ReportFormatError, match="empty"):
        leads.parse(b"")
