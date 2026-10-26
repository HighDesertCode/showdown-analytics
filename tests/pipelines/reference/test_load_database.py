"""Runs the reference loaders against real tables built from sql/ (see tests/pipelines/conftest.py)."""

from pipelines.reference import load
from pipelines.reference import type as type_loader

STATS = {"hp": 100, "atk": 110, "def": 90, "spa": 85, "spd": 90, "spe": 60}
SOURCES = {
    "types": {"water": {}, "ground": {}, "electric": {}, "stellar": {}},
    "abilities": {
        "torrent": {"name": "Torrent", "num": 67},
        "damp": {"name": "Damp", "num": 6},
        "levitate": {"name": "Levitate", "num": 26},
    },
    "ability_text": {"levitate": {"shortDesc": "This Pokemon is immune to Ground."}},
    "species": {
        "swampert": {
            "num": 260,
            "name": "Swampert",
            "types": ["Water", "Ground"],
            "baseStats": STATS,
            "abilities": {"0": "Torrent", "H": "Damp"},
        },
        "rotomwash": {
            "num": 479,
            "name": "Rotom-Wash",
            "baseSpecies": "Rotom",
            "forme": "Wash",
            "types": ["Electric", "Water"],
            "baseStats": STATS,
            "abilities": {"0": "Levitate"},
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
    },
    "moves": {
        "scald": {
            "num": 503,
            "name": "Scald",
            "type": "Water",
            "category": "Special",
            "basePower": 80,
            "accuracy": 100,
            "pp": 15,
            "priority": 0,
            "target": "normal",
            "secondary": {"chance": 30, "status": "brn"},
        },
        "stealthrock": {
            "num": 446,
            "name": "Stealth Rock",
            "type": "Ground",
            "category": "Status",
            "basePower": 0,
            "accuracy": True,
            "pp": 20,
            "priority": 0,
            "target": "foeSide",
            "sideCondition": "stealthrock",
        },
    },
    "move_text": {"scald": {"shortDesc": "30% chance to burn the target. Thaws target."}},
    "items": {
        "leftovers": {"name": "Leftovers", "num": 234},
        "sitrusberry": {"name": "Sitrus Berry", "num": 158, "isBerry": True},
    },
    "item_text": {},
    "natures": {"adamant": {"name": "Adamant", "plus": "atk", "minus": "spa"}, "hardy": {"name": "Hardy"}},
}


def test_load_all_fills_and_links_every_table(conn):
    counts = load.load_all(conn, SOURCES)

    assert counts == {
        "type": 3,
        "ability": 3,
        "species": 2,
        "species_ability": 3,
        "move": 2,
        "move_effect": 2,
        "item": 2,
        "nature": 2,
    }
    swampert = conn.execute(
        """
        SELECT t1.name, t2.name, string_agg(sa.slot || ':' || a.name, ',' ORDER BY sa.slot)
        FROM reference.species s
        JOIN reference.type t1 ON t1.type_id = s.type_1_id
        JOIN reference.type t2 ON t2.type_id = s.type_2_id
        JOIN reference.species_ability sa USING (species_id)
        JOIN reference.ability a USING (ability_id)
        WHERE s.showdown_id = 'swampert'
        GROUP BY 1, 2
        """
    ).fetchone()
    assert swampert == ("Water", "Ground", "0:Torrent,H:Damp")
    stealth_rock = conn.execute(
        """
        SELECT m.accuracy, e.is_secondary, e.affects, e.field_effect
        FROM reference.move m JOIN reference.move_effect e USING (move_id)
        WHERE m.showdown_id = 'stealthrock'
        """
    ).fetchone()
    assert stealth_rock == (None, False, "target", "stealthrock")


def test_rerun_inserts_nothing_and_uses_no_ids(conn):
    load.load_all(conn, SOURCES)
    max_type_id = conn.execute("SELECT max(type_id) FROM reference.type").fetchone()

    counts = load.load_all(conn, SOURCES)
    type_loader.load(conn, {"fire": {}})
    fire = conn.execute("SELECT type_id FROM reference.type WHERE showdown_id = 'fire'").fetchone()

    assert set(counts.values()) == {0}
    assert max_type_id is not None and fire == (max_type_id[0] + 1,)
