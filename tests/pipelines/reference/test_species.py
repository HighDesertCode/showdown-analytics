from pipelines.reference import species

STATS = {"hp": 50, "atk": 65, "def": 107, "spa": 105, "spd": 107, "spe": 86}
POKEDEX = {
    "rotomwash": {
        "num": 479,
        "name": "Rotom-Wash",
        "baseSpecies": "Rotom",
        "forme": "Wash",
        "types": ["Electric", "Water"],
        "baseStats": STATS,
        "abilities": {"0": "Levitate"},
    },
    "greninja": {
        "num": 658,
        "name": "Greninja",
        "types": ["Water", "Dark"],
        "baseStats": STATS,
        "abilities": {"0": "Torrent", "H": "Protean", "S": "Battle Bond"},
    },
    "vivillonfancy": {"name": "Vivillon-Fancy", "isCosmeticForme": True},
    "missingno": {
        "num": 0,
        "name": "MissingNo.",
        "types": ["Bird", "Normal"],
        "baseStats": STATS,
        "abilities": {"0": ""},
        "isNonstandard": "Custom",
    },
}
TYPE_IDS = {"electric": 1, "water": 2, "dark": 3}


def test_rows_skip_cosmetic_and_custom_entries():
    assert [row[0] for row in species.rows(POKEDEX, TYPE_IDS)] == ["rotomwash", "greninja"]


def test_rows_map_types_and_forms():
    rotom = species.rows(POKEDEX, TYPE_IDS)[0]

    assert rotom == ("rotomwash", "Rotom-Wash", 479, "Rotom", "Wash", 1, 2, 50, 65, 107, 105, 107, 86, None)


def test_ability_rows_skip_special_slot():
    species_ids = {"rotomwash": 10, "greninja": 11}
    ability_ids = {"levitate": 1, "torrent": 2, "protean": 3, "battlebond": 4}

    assert species.ability_rows(POKEDEX, species_ids, ability_ids) == [(10, "0", 1), (11, "0", 2), (11, "H", 3)]
