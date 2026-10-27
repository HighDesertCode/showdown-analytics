import pytest

from pipelines.raw import text_table
from pipelines.raw.common import ReportFormatError

BORDER = "+ ---- + --------- +"
TABLE = ["Header line", BORDER, "| Rank | Pokemon   |", BORDER, "| 1    | Dragapult |", BORDER]


def test_rows_returns_line_numbers_and_cells():
    assert text_table.rows(TABLE, 1, ["Rank", "Pokemon"]) == [(5, ["1", "Dragapult"])]


def test_rows_accepts_an_empty_table():
    assert text_table.rows(TABLE[:4] + [BORDER], 1, ["Rank", "Pokemon"]) == []


@pytest.mark.parametrize(
    ("lines", "message"),
    [
        (TABLE[:3], "expected a table starting on line 2"),
        (["Header line", "+----+", *TABLE[2:]], "line 2"),
        (TABLE[:-1], "line 5"),
        (["Header line", BORDER, "Rank | Pokemon", *TABLE[3:]], "line 3: expected a table row"),
    ],
)
def test_rows_rejects_malformed_tables(lines, message):
    with pytest.raises(ReportFormatError, match=message):
        text_table.rows(lines, 1, ["Rank", "Pokemon"])


def test_percent_keeps_printed_precision():
    assert str(text_table.percent("15.95180%", 1)) == "15.95180"
