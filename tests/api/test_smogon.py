from datetime import UTC, date, datetime

import pytest

RETRIEVED_AT = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
SEPTEMBER = date(2026, 9, 1)
AUGUST = date(2026, 8, 1)


def add_report(insert, month=SEPTEMBER, baseline=1630, team_type=None, first_file_id=1):
    """A report scope with its usage and chaos files."""
    usage_id, chaos_id = first_file_id, first_file_id + 1
    insert(
        "available_month",
        format="gen9monotype",
        report_month=month,
        baseline=baseline,
        file_count=77,
        last_retrieved_at=RETRIEVED_AT,
    )
    for source_file_id, family in ((usage_id, "usage"), (chaos_id, "chaos")):
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
        usage_source_file_id=1,
        chaos_source_file_id=2,
    )


def test_months_lists_newest_first(client, insert):
    add_report(insert, month=AUGUST, first_file_id=1)
    add_report(insert, month=SEPTEMBER, first_file_id=3)

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
    add_report(insert, month=SEPTEMBER, first_file_id=3)
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
    add_report(insert, team_type="water", first_file_id=3)
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
        ({"month": "2026-08"}, "No Smogon report for gen9monotype in 2026-08 at baseline 1630 for all teams"),
        ({"team_type": "stellar"}, "No Smogon report for gen9monotype in 2026-09 at baseline 1630 for stellar teams"),
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
