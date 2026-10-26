from pipelines.reference import type as type_loader


def test_rows_capitalizes_names_and_skips_stellar():
    typechart = {"water": {}, "ground": {}, "stellar": {}}

    assert type_loader.rows(typechart) == [("water", "Water"), ("ground", "Ground")]
