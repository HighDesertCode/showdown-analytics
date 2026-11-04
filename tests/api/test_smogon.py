from datetime import UTC, date, datetime

import pytest

RETRIEVED_AT = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
SEPTEMBER = date(2026, 9, 1)
AUGUST = date(2026, 8, 1)
TYPE_IDS = {"water": 11, "ground": 5}


def add_report(insert, month=SEPTEMBER, baseline=1630, team_type=None, first_file_id=1):
    """A report scope with its usage, chaos, leads, and metagame files, numbered from first_file_id."""
    usage_id, chaos_id, leads_id, metagame_id = range(first_file_id, first_file_id + 4)
    insert(
        "available_month",
        format="gen9monotype",
        report_month=month,
        baseline=baseline,
        file_count=77,
        last_retrieved_at=RETRIEVED_AT,
    )
    files = ((usage_id, "usage"), (chaos_id, "chaos"), (leads_id, "leads"), (metagame_id, "metagame"))
    for source_file_id, family in files:
        insert(
            "source_file",
            source_file_id=source_file_id,
            family=family,
            format="gen9monotype",
            report_month=month,
            baseline=baseline,
            team_type=team_type,
            url=f"https://www.smogon.com/stats/{month:%Y-%m}/{family}/{source_file_id}",
            content_sha256="ab" * 32,
            byte_size=1024,
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
        metagame_source_file_id=metagame_id,
        avg_team_weight=0.25,
        stalliness_mean=-0.4,
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
    add_report(insert, month=SEPTEMBER, first_file_id=11)

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
    add_report(insert, month=SEPTEMBER, first_file_id=11)
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
    add_report(insert, team_type="water", first_file_id=11)
    add_usage(insert, 1, "greattusk", "Great Tusk")
    add_usage(insert, 1, "swampert", "Swampert", team_type="water")

    body = client.get("/v1/smogon/usage", params={"team_type": team_type}).json()

    assert body["scope"]["team_type"] == "water"
    assert [row["species"] for row in body["data"]] == ["swampert"]


def test_usage_treats_overall_as_all_teams(client, insert):
    add_report(insert)
    add_report(insert, team_type="water", first_file_id=11)
    add_usage(insert, 1, "greattusk", "Great Tusk")
    add_usage(insert, 1, "swampert", "Swampert", team_type="water")

    body = client.get("/v1/smogon/usage", params={"team_type": "overall"}).json()

    assert body["scope"]["team_type"] is None
    assert [row["species"] for row in body["data"]] == ["greattusk"]


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


def add_rows(insert, table, rows, team_type=None):
    """Swampert's rows in one of its sections, in the September 1630 scope."""
    for row in rows:
        insert(
            table,
            format="gen9monotype",
            report_month=SEPTEMBER,
            baseline=1630,
            team_type=team_type,
            species_id=1,
            species="swampert",
            species_name="Swampert",
            source_file_id=2,
            **row,
        )


def add_swampert(insert):
    add_report(insert)
    add_usage(insert, 1, "swampert", "Swampert")
    add_rows(
        insert,
        "pokemon_move",
        [
            {"move_id": number, "move": f"move{number:02}", "move_name": f"Move {number}", "share": number / 20}
            for number in range(1, 13)
        ],
    )
    add_rows(
        insert,
        "pokemon_item",
        [
            {"has_item": True, "item_id": 1, "item": "leftovers", "item_name": "Leftovers", "share": 0.59},
            {"has_item": False, "item_id": None, "item": None, "item_name": None, "share": 0.41},
        ],
    )
    add_rows(
        insert,
        "pokemon_counter",
        [
            {
                "opponent_species_id": opponent_id,
                "opponent_species": opponent,
                "opponent_species_name": opponent.title(),
                "encounters": 100.0,
                "ko_or_switch_rate": 0.7,
                "ko_or_switch_rate_std_dev": 0.05,
                "score": score,
            }
            for opponent_id, opponent, score in ((2, "ogerpon", 0.3), (3, "meowscarada", 0.5))
        ],
    )


def test_pokemon_profile_has_usage_and_the_top_ten_of_each_section(client, insert):
    add_swampert(insert)
    insert(
        "pokemon_lead",
        format="gen9monotype",
        report_month=SEPTEMBER,
        baseline=1630,
        species_id=1,
        species="swampert",
        species_name="Swampert",
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


@pytest.mark.parametrize("path", ["/v1/smogon/pokemon/!!!", "/v1/smogon/pokemon/!!!/moves"])
def test_pokemon_rejects_a_species_with_no_letters_or_digits(client, insert, path):
    response = client.get(path)

    assert response.status_code == 422
    assert response.json() == {"detail": "'!!!' isn't a species"}


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


def test_leads_ranks_pokemon_and_cites_the_leads_file(client, insert):
    add_report(insert)
    for rank, species in enumerate(["swampert", "greattusk"], start=1):
        insert(
            "pokemon_lead",
            format="gen9monotype",
            report_month=SEPTEMBER,
            baseline=1630,
            species_id=rank,
            species=species,
            species_name=species.title(),
            rank=rank,
            lead_share=0.1 / rank,
            raw_count=100 // rank,
            raw_lead_share=0.1 / rank,
            source_file_id=3,
        )

    body = client.get("/v1/smogon/leads").json()

    assert [(row["rank"], row["species"]) for row in body["data"]] == [(1, "swampert"), (2, "greattusk")]
    assert [source["family"] for source in body["sources"]] == ["leads"]
    assert body["page"]["total"] == 2


def test_metagame_has_the_sample_size_and_tags_most_common_first(client, insert):
    add_report(insert, team_type="water")
    for tag, tag_team_type, share in (("rain", None, 0.3), ("monowater", "water", 1.0), ("stall", None, 0.1)):
        insert(
            "metagame_tag",
            format="gen9monotype",
            report_month=SEPTEMBER,
            baseline=1630,
            team_type="water",
            tag=tag,
            tag_team_type=tag_team_type,
            share=share,
            source_file_id=4,
        )

    body = client.get("/v1/smogon/metagame", params={"team_type": "water"}).json()

    assert body["data"]["battle_count"] == 63572
    assert body["data"]["stalliness_mean"] == -0.4
    assert [tag["tag"] for tag in body["data"]["tags"]] == ["monowater", "rain", "stall"]
    assert [source["family"] for source in body["sources"]] == ["metagame", "usage"]


def add_chart(insert, month=SEPTEMBER, baseline=1630, source_file_id=50):
    """A matchup chart: water and ground against each other and themselves, and their viability scores."""
    insert(
        "available_month",
        format="gen9monotype",
        report_month=month,
        baseline=baseline,
        file_count=77,
        last_retrieved_at=RETRIEVED_AT,
    )
    insert(
        "source_file",
        source_file_id=source_file_id,
        family="matchup_chart",
        format="gen9monotype",
        report_month=month,
        baseline=baseline,
        url=f"https://www.smogon.com/stats/{month:%Y-%m}/monotype/matchupcharts/{baseline}",
        content_sha256="cd" * 32,
        byte_size=2048,
        retrieved_at=RETRIEVED_AT,
    )
    rates = {("water", "ground"): 0.72636, ("ground", "water"): 0.27364}
    for type_ in ("water", "ground"):
        for opponent in ("water", "ground"):
            insert(
                "type_matchup",
                format="gen9monotype",
                report_month=month,
                baseline=baseline,
                type_id=TYPE_IDS[type_],
                type=type_,
                type_name=type_.title(),
                opponent_type_id=TYPE_IDS[opponent],
                opponent_type=opponent,
                opponent_type_name=opponent.title(),
                is_mirror=type_ == opponent,
                wins=100.0,
                win_rate=rates.get((type_, opponent)),
                source_file_id=source_file_id,
            )
    for rank, type_, score in ((1, "water", 2.5), (2, "ground", 1.2)):
        insert(
            "type_viability",
            format="gen9monotype",
            report_month=month,
            baseline=baseline,
            type_id=TYPE_IDS[type_],
            type=type_,
            type_name=type_.title(),
            viability_score=score,
            rank=rank,
            source_file_id=source_file_id,
        )


def test_type_matchups_lists_every_pairing_from_the_chart(client, insert):
    add_chart(insert)

    body = client.get("/v1/smogon/type-matchups").json()

    assert body["scope"] == {
        "source": "smogon",
        "format": "gen9monotype",
        "month": "2026-09",
        "baseline": 1630,
        "team_type": None,
    }
    assert [(row["type"], row["opponent_type"], row["win_rate"]) for row in body["data"]] == [
        ("ground", "ground", None),
        ("ground", "water", 0.27364),
        ("water", "ground", 0.72636),
        ("water", "water", None),
    ]
    assert [source["source_file_id"] for source in body["sources"]] == [50]


def test_type_matchups_filters_by_type_and_opponent(client, insert):
    add_chart(insert)

    body = client.get("/v1/smogon/type-matchups", params={"type": "Water", "opponent_type": "ground"}).json()

    assert [(row["type"], row["opponent_type"]) for row in body["data"]] == [("water", "ground")]
    assert body["page"]["total"] == 1


def test_type_matchups_reject_a_type_with_no_letters_or_digits(client, insert):
    add_chart(insert)

    response = client.get("/v1/smogon/type-matchups", params={"type": "!"})

    assert response.status_code == 422
    assert response.json() == {"detail": "'!' isn't a type"}


def test_type_matchups_explains_a_missing_chart(client, insert):
    add_report(insert)

    response = client.get("/v1/smogon/type-matchups")

    assert response.status_code == 404
    assert response.json() == {"detail": "No Smogon matchup chart for gen9monotype in 2026-09 at baseline 1630"}


def test_type_viability_ranks_types(client, insert):
    add_chart(insert)

    body = client.get("/v1/smogon/type-viability").json()

    assert [(row["rank"], row["type"], row["viability_score"]) for row in body["data"]] == [
        (1, "water", 2.5),
        (2, "ground", 1.2),
    ]


def test_source_file_shows_its_version_and_scope(client, insert):
    add_report(insert, team_type="water")

    body = client.get("/v1/smogon/source-files/2").json()

    assert body["scope"] == {
        "source": "smogon",
        "format": "gen9monotype",
        "month": "2026-09",
        "baseline": 1630,
        "team_type": "water",
    }
    assert body["data"]["family"] == "chaos"
    assert body["data"]["content_sha256"] == "ab" * 32


def test_source_file_explains_a_missing_file(client, insert):
    assert client.get("/v1/smogon/source-files/999").json() == {"detail": "No Smogon source file 999"}
