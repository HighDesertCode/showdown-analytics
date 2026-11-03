from datetime import UTC, date, datetime

import pytest

RETRIEVED_AT = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
SEPTEMBER = date(2026, 9, 1)
AUGUST = date(2026, 8, 1)


def add_report(insert, month=SEPTEMBER, baseline=1630, team_type=None, first_file_id=1):
    """A report scope with its usage, chaos, and leads files, numbered from first_file_id."""
    usage_id, chaos_id, leads_id = first_file_id, first_file_id + 1, first_file_id + 2
    insert(
        "available_month",
        format="gen9monotype",
        report_month=month,
        baseline=baseline,
        file_count=77,
        last_retrieved_at=RETRIEVED_AT,
    )
    for source_file_id, family in ((usage_id, "usage"), (chaos_id, "chaos"), (leads_id, "leads")):
        insert(
            "source_file",
            source_file_id=source_file_id,
            family=family,
            format="gen9monotype",
            report_month=month,
            baseline=baseline,
            team_type=team_type,
            url=f"https://www.smogon.com/stats/{month:%Y-%m}/{family}/{source_file_id}",
            retrieved_at=RETRIEVED_AT,
        )
    insert(
        "report",
        format="gen9monotype",
        report_month=month,
        baseline=baseline,
        team_type=team_type,
        battle_count=63572,
        usage_source_file_id=usage_id,
        chaos_source_file_id=chaos_id,
        leads_source_file_id=leads_id,
    )


def add_usage(insert, rank, species, species_name, month=SEPTEMBER, baseline=1630, team_type=None):
    insert(
        "pokemon_usage",
        format="gen9monotype",
        report_month=month,
        baseline=baseline,
        team_type=team_type,
        species_id=rank,
        species=species,
        species_name=species_name,
        rank=rank,
        usage_share=0.5 / rank,
        raw_count=1000 // rank,
        raw_share=0.4 / rank,
        real_count=900 // rank,
        real_share=0.1 / rank,
        battle_appearance_rate=0.9,
        usage_source_file_id=1,
        chaos_source_file_id=2,
    )


def test_months_lists_newest_first(client, insert):
    add_report(insert, month=AUGUST, first_file_id=1)
    add_report(insert, month=SEPTEMBER, first_file_id=4)

    body = client.get("/v1/smogon/months").json()

    assert body["scope"] == {
        "source": "smogon",
        "format": "gen9monotype",
        "month": None,
        "baseline": None,
        "team_type": None,
    }
    assert [row["month"] for row in body["data"]] == ["2026-09", "2026-08"]
    assert body["data"][0]["file_count"] == 77


def test_usage_defaults_to_the_latest_month_at_1630_for_all_teams(client, insert):
    add_report(insert, month=AUGUST, first_file_id=1)
    add_report(insert, month=SEPTEMBER, first_file_id=4)
    add_usage(insert, 1, "greattusk", "Great Tusk", month=AUGUST)
    add_usage(insert, 1, "swampert", "Swampert")
    add_usage(insert, 2, "ninetalesalola", "Ninetales-Alola")

    body = client.get("/v1/smogon/usage").json()

    assert body["scope"] == {
        "source": "smogon",
        "format": "gen9monotype",
        "month": "2026-09",
        "baseline": 1630,
        "team_type": None,
    }
    assert [row["species"] for row in body["data"]] == ["swampert", "ninetalesalola"]
    assert body["data"][0]["usage_share"] == 0.5
    assert body["page"] == {"limit": 50, "offset": 0, "total": 2}


def test_usage_cites_the_scopes_usage_and_chaos_files(client, insert):
    add_report(insert)
    add_usage(insert, 1, "swampert", "Swampert")

    sources = client.get("/v1/smogon/usage").json()["sources"]

    assert [(source["source_file_id"], source["family"]) for source in sources] == [(2, "chaos"), (1, "usage")]
    assert sources[1]["url"] == "https://www.smogon.com/stats/2026-09/usage/1"


@pytest.mark.parametrize("team_type", ["water", "Water", "WATER"])
def test_usage_accepts_a_team_type_by_name_or_id(client, insert, team_type):
    add_report(insert)
    add_report(insert, team_type="water", first_file_id=4)
    add_usage(insert, 1, "greattusk", "Great Tusk")
    add_usage(insert, 1, "swampert", "Swampert", team_type="water")

    body = client.get("/v1/smogon/usage", params={"team_type": team_type}).json()

    assert body["scope"]["team_type"] == "water"
    assert [row["species"] for row in body["data"]] == ["swampert"]


def test_usage_pages(client, insert):
    add_report(insert)
    for rank, species in enumerate(["swampert", "greattusk", "corviknight"], start=1):
        add_usage(insert, rank, species, species.title())

    body = client.get("/v1/smogon/usage", params={"limit": 1, "offset": 1}).json()

    assert [row["species"] for row in body["data"]] == ["greattusk"]
    assert body["page"] == {"limit": 1, "offset": 1, "total": 3}


@pytest.mark.parametrize(
    ("params", "detail"),
    [
        ({"month": "2026-08"}, "No Smogon report for gen9monotype in 2026-08 at baseline 1630 (all teams)"),
        ({"team_type": "stellar"}, "No Smogon report for gen9monotype in 2026-09 at baseline 1630 (stellar teams)"),
        ({"baseline": 1500}, "No Smogon statistics for gen9monotype at baseline 1500"),
    ],
)
def test_usage_explains_a_missing_scope(client, insert, params, detail):
    add_report(insert)

    response = client.get("/v1/smogon/usage", params=params)

    assert response.status_code == 404
    assert response.json() == {"detail": detail}


@pytest.mark.parametrize(
    "params", [{"month": "2026-13"}, {"month": "September"}, {"limit": 501}, {"offset": -1}, {"team_type": "!"}]
)
def test_usage_rejects_invalid_parameters(client, insert, params):
    add_report(insert)

    response = client.get("/v1/smogon/usage", params=params)

    assert response.status_code == 422


def add_rows(insert, table, species, rows, team_type=None):
    """Rows of one of a Pokémon's sections in the September 1630 scope."""
    for row in rows:
        insert(
            table,
            format="gen9monotype",
            report_month=SEPTEMBER,
            baseline=1630,
            team_type=team_type,
            species=species,
            source_file_id=2,
            **row,
        )


def add_swampert(insert):
    add_report(insert)
    add_usage(insert, 1, "swampert", "Swampert")
    add_rows(
        insert,
        "pokemon_move",
        "swampert",
        [{"move": f"move{number:02}", "move_name": f"Move {number}", "share": number / 20} for number in range(1, 13)],
    )
    add_rows(
        insert,
        "pokemon_item",
        "swampert",
        [
            {"has_item": True, "item": "leftovers", "item_name": "Leftovers", "share": 0.59},
            {"has_item": False, "item": None, "item_name": None, "share": 0.41},
        ],
    )
    add_rows(
        insert,
        "pokemon_counter",
        "swampert",
        [
            {
                "opponent_species": opponent,
                "opponent_species_name": opponent.title(),
                "encounters": 100.0,
                "ko_or_switch_rate": 0.7,
                "ko_or_switch_rate_std_dev": 0.05,
                "score": score,
            }
            for opponent, score in (("ogerpon", 0.3), ("meowscarada", 0.5))
        ],
    )


def test_pokemon_profile_has_usage_and_the_top_ten_of_each_section(client, insert):
    add_swampert(insert)
    insert(
        "pokemon_lead",
        format="gen9monotype",
        report_month=SEPTEMBER,
        baseline=1630,
        species="swampert",
        rank=3,
        lead_share=0.04,
        raw_count=812,
        raw_lead_share=0.03,
        source_file_id=3,
    )

    body = client.get("/v1/smogon/pokemon/swampert").json()

    profile = body["data"]
    assert body["scope"]["month"] == "2026-09"
    assert profile["usage"]["rank"] == 1
    assert profile["usage"]["battle_appearance_rate"] == 0.9
    assert profile["lead"] == {"rank": 3, "lead_share": 0.04, "raw_count": 812, "raw_lead_share": 0.03}
    assert [move["move"] for move in profile["moves"]] == [f"move{number:02}" for number in range(12, 2, -1)]
    assert [item["item"] for item in profile["items"]] == ["leftovers", None]
    assert [counter["species"] for counter in profile["counters"]] == ["meowscarada", "ogerpon"]
    assert profile["abilities"] == []
    assert [source["family"] for source in body["sources"]] == ["chaos", "leads", "usage"]
    assert "page" not in body or body["page"] is None


def test_pokemon_profile_accepts_a_display_name_and_has_no_lead_when_it_never_led(client, insert):
    add_swampert(insert)

    body = client.get("/v1/smogon/pokemon/Swampert").json()

    assert body["data"]["usage"]["species"] == "swampert"
    assert body["data"]["lead"] is None


def test_pokemon_profile_explains_a_pokemon_missing_from_the_scope(client, insert):
    add_swampert(insert)

    response = client.get("/v1/smogon/pokemon/Great Tusk")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "No Smogon usage for greattusk for gen9monotype in 2026-09 at baseline 1630 (all teams)"
    }


def test_pokemon_section_lists_every_row_by_page(client, insert):
    add_swampert(insert)

    body = client.get("/v1/smogon/pokemon/swampert/moves", params={"limit": 5, "offset": 10}).json()

    assert [move["move"] for move in body["data"]] == ["move02", "move01"]
    assert body["page"] == {"limit": 5, "offset": 10, "total": 12}
    assert [source["family"] for source in body["sources"]] == ["chaos"]


def test_pokemon_section_orders_counters_by_score(client, insert):
    add_swampert(insert)

    body = client.get("/v1/smogon/pokemon/swampert/counters").json()

    assert [(counter["species"], counter["score"]) for counter in body["data"]] == [
        ("meowscarada", 0.5),
        ("ogerpon", 0.3),
    ]


def test_pokemon_section_rejects_an_unknown_section(client, insert):
    add_swampert(insert)

    assert client.get("/v1/smogon/pokemon/swampert/natures").status_code == 422


def test_openapi_schema_builds(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/v1/smogon/pokemon/{species}/{section}" in response.json()["paths"]
