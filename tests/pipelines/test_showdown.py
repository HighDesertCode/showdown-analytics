import pytest

from pipelines import showdown


def test_parse_json():
    assert showdown.parse('{"swampert": {"num": 260}}') == {"swampert": {"num": 260}}


def test_parse_client_js_export():
    text = "exports.BattleTypeChart = {water:{damageTaken:{Fire:2}},ground:{damageTaken:{}}};"

    assert showdown.parse(text) == {"water": {"damageTaken": {"Fire": 2}}, "ground": {"damageTaken": {}}}


def test_parse_typescript_with_braces_in_type_annotation():
    text = """export const ItemsText: { [id: IDEntry]: ItemText } = {
\tleftovers: {
\t\tname: "Leftovers",
\t\tshortDesc: 'At the end of every turn, holder restores 1/16 of its max HP.',
\t},
};
"""

    assert showdown.parse(text) == {
        "leftovers": {"name": "Leftovers", "shortDesc": "At the end of every turn, holder restores 1/16 of its max HP."}
    }


def test_parse_rejects_text_without_data():
    with pytest.raises(ValueError):
        showdown.parse("export const nothing = 1;")


@pytest.mark.parametrize(
    ("name", "expected"),
    [("Heavy-Duty Boots", "heavydutyboots"), ("Rotom-Wash", "rotomwash"), ("Mr. Mime", "mrmime"), ("Water", "water")],
)
def test_to_id(name, expected):
    assert showdown.to_id(name) == expected


def test_load_fetches_source_url(monkeypatch):
    fetched = []
    monkeypatch.setattr(showdown, "fetch", lambda url: fetched.append(url) or "{}")

    assert showdown.load("species") == {}
    assert fetched == ["https://play.pokemonshowdown.com/data/pokedex.json"]


def test_load_rejects_unknown_source():
    with pytest.raises(KeyError):
        showdown.load("pokeapi")
