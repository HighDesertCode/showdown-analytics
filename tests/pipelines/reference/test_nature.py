from pipelines.reference import nature


def test_rows_leave_neutral_stats_empty():
    natures = {
        "adamant": {"name": "Adamant", "plus": "atk", "minus": "spa"},
        "hardy": {"name": "Hardy"},
    }

    assert nature.rows(natures) == [("adamant", "Adamant", "atk", "spa"), ("hardy", "Hardy", None, None)]
