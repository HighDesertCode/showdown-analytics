from decimal import Decimal

import pytest

from pipelines.raw import usage
from pipelines.raw.common import ReportFormatError

BORDER = "+ ---- + ------------------ + --------- + ------ + ------- + ------ + ------- +"
# A trimmed real report; the Ogerpon-Hearthflame row is wider than its column, as in Smogon's files.
REPORT = f"""Total battles: 63572
Avg. weight/team: 0.192
{BORDER}
| Rank | Pokemon            | Usage %   | Raw    | %       | Real   | %       |
{BORDER}
| 1    | Dragapult          | 15.95180% | 15179  | 11.938% | 11396  | 11.603% |
| 46   | Ogerpon-Hearthflame |  4.73609% | 7195   |  5.659% | 5412   |  5.511% |
{BORDER}
"""


def test_parse_builds_rows():
    report = usage.parse(REPORT.encode())

    assert report.info == (63572, Decimal("0.192"))
    assert report.pokemon == [
        (1, "Dragapult", Decimal("15.95180"), 15179, Decimal("11.938"), 11396, Decimal("11.603")),
        (46, "Ogerpon-Hearthflame", Decimal("4.73609"), 7195, Decimal("5.659"), 5412, Decimal("5.511")),
    ]


def test_parse_accepts_a_report_without_pokemon():
    lines = REPORT.splitlines()

    assert usage.parse("\n".join(lines[:5] + lines[-1:]).encode()).pokemon == []


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("Total battles: 63572", "Battles: 63572", "line 1"),
        ("Avg. weight/team: 0.192", "Avg. weight/team: high", "line 2"),
        ("| Usage %   |", "| Weighted  |", "line 4: expected columns"),
        ("| 15179  |", "| 15179  | 1 |", "line 6: expected 7 cells"),
        ("15.95180%", "15.95180", "line 6"),
        ("| 7195   |", "| many   |", "line 7"),
    ],
)
def test_parse_rejects_unexpected_shapes(old, new, message):
    with pytest.raises(ReportFormatError, match=message):
        usage.parse(REPORT.replace(old, new, 1).encode())


def test_parse_rejects_missing_closing_border():
    with pytest.raises(ReportFormatError, match="line 7"):
        usage.parse(REPORT.removesuffix(BORDER + "\n").encode())
