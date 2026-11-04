import pytest


def test_species_entry_by_name_has_its_base_stats(client, insert):
    insert(
        "species",
        species_id=1,
        species="ninetalesalola",
        species_name="Ninetales-Alola",
        dex_number=38,
        base_species="Ninetales",
        forme="Alola",
        type_1="Ice",
        type_2="Fairy",
        hp=73,
        atk=67,
        spa=81,
        spd=100,
        spe=109,
        **{"def": 75},
    )

    body = client.get("/v1/reference/species/Ninetales-Alola").json()

    assert body["scope"] == {"source": "reference"}
    assert body["data"]["species"] == "ninetalesalola"
    assert (body["data"]["def"], body["data"]["spe"]) == (75, 109)
    assert body["data"]["nonstandard"] is None


def test_entries_list_by_showdown_id_and_page(client, insert):
    for number, (item, name) in enumerate(
        (("leftovers", "Leftovers"), ("heavydutyboots", "Heavy-Duty Boots"), ("choicescarf", "Choice Scarf")), start=1
    ):
        insert("item", item_id=number, item=item, item_name=name, is_berry=False)

    body = client.get("/v1/reference/items", params={"limit": 2}).json()

    assert [row["item"] for row in body["data"]] == ["choicescarf", "heavydutyboots"]
    assert body["page"] == {"limit": 2, "offset": 0, "total": 3}


def test_move_entry_keeps_a_null_accuracy_for_moves_that_cant_miss(client, insert):
    insert(
        "move",
        move_id=1,
        move="aerialace",
        move_name="Aerial Ace",
        type="Flying",
        category="Physical",
        base_power=60,
        accuracy=None,
        pp=20,
        priority=0,
        target="any",
    )

    body = client.get("/v1/reference/moves/aerialace").json()

    assert body["data"]["accuracy"] is None


@pytest.mark.parametrize(
    ("path", "detail"),
    [("/v1/reference/natures/Bold", "No natures entry 'bold'"), ("/v1/reference/types/!!", "No types entry '!!'")],
)
def test_entry_explains_a_missing_entry(client, insert, path, detail):
    response = client.get(path)

    assert response.status_code == 404
    assert response.json() == {"detail": detail}


def test_unknown_kind_is_rejected(client, insert):
    assert client.get("/v1/reference/berries").status_code == 422
