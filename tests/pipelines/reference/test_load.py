from typing import cast

from psycopg import Connection

from pipelines import showdown
from pipelines.reference import load


def test_load_all_runs_loaders_in_foreign_key_order(monkeypatch):
    calls = []

    def fake(name, result):
        def fake_load(conn, *data):
            calls.append((name, conn, data))
            return result

        return fake_load

    monkeypatch.setattr(load.type_loader, "load", fake("type", 18))
    monkeypatch.setattr(load.ability, "load", fake("ability", 321))
    monkeypatch.setattr(load.species, "load", fake("species", (1462, 3191)))
    monkeypatch.setattr(load.move, "load", fake("move", (954, 440)))
    monkeypatch.setattr(load.item, "load", fake("item", 587))
    monkeypatch.setattr(load.nature, "load", fake("nature", 25))
    sources = {name: {"source": name} for name in showdown.SOURCES}
    conn = cast(Connection, object())  # Stand-in; the fake loaders never use it.

    counts = load.load_all(conn, sources)

    assert [name for name, _, _ in calls] == ["type", "ability", "species", "move", "item", "nature"]
    assert all(passed is conn for _, passed, _ in calls)
    assert calls[1][2] == ({"source": "abilities"}, {"source": "ability_text"})
    assert counts == {
        "type": 18,
        "ability": 321,
        "species": 1462,
        "species_ability": 3191,
        "move": 954,
        "move_effect": 440,
        "item": 587,
        "nature": 25,
    }
