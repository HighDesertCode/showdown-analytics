from decimal import Decimal

import pytest

from pipelines.raw import metagame
from pipelines.raw.common import ReportFormatError

# A trimmed real report.
REPORT = """monotype..........100.00000%
stall.............52.49034%
monowater.........8.59354%

Stalliness (mean: 1.730)
    |#
-1.0|##
 0.0|###########
+1.0|
more negative = more offensive, more positive = more stall
one # = 0.63%
"""


def test_parse_keeps_tags_and_mean():
    report = metagame.parse(REPORT.encode())

    assert report.stalliness_mean == Decimal("1.730")
    assert report.tags == [
        ("monotype", Decimal("100.00000")),
        ("stall", Decimal("52.49034")),
        ("monowater", Decimal("8.59354")),
    ]


def test_parse_accepts_negative_mean():
    report = metagame.parse(REPORT.replace("mean: 1.730", "mean: -0.250").encode())

    assert report.stalliness_mean == Decimal("-0.250")


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("stall.............52.49034%", "stall 52.49034%", "line 2"),
        ("monowater.........8.59354%\n\n", "monowater.........8.59354%\n", "blank line"),
        ("Stalliness (mean: 1.730)", "Stalliness: 1.730", "line 5"),
        ("-1.0|##", "-1.0|==", "line 7"),
        ("one # = 0.63%", "one # = 0.63 teams", "line 11"),
    ],
)
def test_parse_rejects_unexpected_shapes(old, new, message):
    with pytest.raises(ReportFormatError, match=message):
        metagame.parse(REPORT.replace(old, new, 1).encode())
