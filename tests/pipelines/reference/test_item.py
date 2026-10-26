from pipelines.reference import item


def test_rows_flag_berries_and_include_description():
    items = {
        "leftovers": {"name": "Leftovers", "num": 234},
        "sitrusberry": {"name": "Sitrus Berry", "num": 158, "isBerry": True},
    }
    item_text = {"leftovers": {"shortDesc": "Restores 1/16 max HP each turn."}}

    assert item.rows(items, item_text) == [
        ("leftovers", "Leftovers", 234, False, "Restores 1/16 max HP each turn.", None),
        ("sitrusberry", "Sitrus Berry", 158, True, None, None),
    ]
