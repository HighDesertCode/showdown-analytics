from pipelines.reference import ability


def test_rows_include_description_and_nonstandard_flag():
    abilities = {
        "levitate": {"name": "Levitate", "num": 26, "rating": 3.5},
        "noability": {"name": "No Ability", "num": 0, "isNonstandard": "Past"},
    }
    ability_text = {"levitate": {"name": "Levitate", "shortDesc": "This Pokemon is immune to Ground."}}

    assert ability.rows(abilities, ability_text) == [
        ("levitate", "Levitate", 26, "This Pokemon is immune to Ground.", None),
        ("noability", "No Ability", 0, None, "Past"),
    ]
