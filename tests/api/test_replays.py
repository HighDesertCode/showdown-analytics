from datetime import UTC, date, datetime

import pytest

SEPTEMBER = date(2026, 9, 1)
AUGUST = date(2026, 8, 1)
TYPE_IDS = {"water": 11, "ground": 5}


def add_sample(insert, month=SEPTEMBER, bands=(1000, 1200, 1400, 1600)):
    for band in bands:
        insert(
            "replay_sample",
            format="gen9monotype",
            report_month=month,
            elo_band=band,
            battle_count=2400,
            rated_battle_count=1700,
            team_count=band // 2,
            typed_team_count=band // 3,
        )


def add_matchup(insert, band, type_, opponent, battles, wins, month=SEPTEMBER):
    insert(
        "replay_type_matchup",
        format="gen9monotype",
        report_month=month,
        elo_band=band,
        type_id=TYPE_IDS[type_],
        type=type_,
        type_name=type_.title(),
        opponent_type_id=TYPE_IDS[opponent],
        opponent_type=opponent,
        opponent_type_name=opponent.title(),
        is_mirror=type_ == opponent,
        battle_count=battles,
        win_count=wins,
        tie_count=0,
        win_rate=None if type_ == opponent else wins / battles,
    )


def test_sample_is_labeled_as_uploaded_replays_and_defaults_to_the_latest_month(client, insert):
    add_sample(insert, month=AUGUST)
    add_sample(insert)

    body = client.get("/v1/replays/sample").json()

    assert body["scope"] == {
        "source": "replays",
        "format": "gen9monotype",
        "month": "2026-09",
        "partial_month": False,
        "elo_band": None,
        "battle_count": 2400,
        "rated_battle_count": 1700,
    }
    assert body["sources"] == []
    assert [row["elo_band"] for row in body["data"]] == [1000, 1200, 1400, 1600]


def this_month():
    return datetime.now(UTC).date().replace(day=1)


def test_sample_defaults_to_the_latest_complete_month_not_the_one_in_progress(client, insert):
    add_sample(insert)
    add_sample(insert, month=this_month())

    body = client.get("/v1/replays/sample").json()

    assert body["scope"]["month"] == "2026-09"
    assert body["scope"]["partial_month"] is False


def test_sample_gives_the_month_in_progress_when_asked_and_flags_it(client, insert):
    add_sample(insert)
    add_sample(insert, month=this_month())

    body = client.get("/v1/replays/sample", params={"month": this_month().strftime("%Y-%m")}).json()

    assert body["scope"]["month"] == this_month().strftime("%Y-%m")
    assert body["scope"]["partial_month"] is True


def test_sample_falls_back_to_the_month_in_progress_when_no_month_is_complete(client, insert):
    add_sample(insert, month=this_month())

    body = client.get("/v1/replays/sample").json()

    assert body["scope"]["partial_month"] is True


def test_sample_filters_by_elo_band(client, insert):
    add_sample(insert)

    body = client.get("/v1/replays/sample", params={"elo_band": 1400}).json()

    assert body["scope"]["elo_band"] == 1400
    assert body["data"] == [{"elo_band": 1400, "team_count": 700, "typed_team_count": 466}]


@pytest.mark.parametrize("params", [{"elo_band": 1300}, {"elo_band": "high"}, {"month": "2026-9"}])
def test_replay_statistics_reject_invalid_parameters(client, insert, params):
    add_sample(insert)

    assert client.get("/v1/replays/sample", params=params).status_code == 422


def test_replay_statistics_explain_a_month_without_replays(client, insert):
    add_sample(insert)

    response = client.get("/v1/replays/type-matchups", params={"month": "2026-02"})

    assert response.status_code == 404
    assert response.json() == {"detail": "No replay statistics for gen9monotype in 2026-02"}


def test_type_matchups_filter_by_band_type_and_opponent(client, insert):
    add_sample(insert)
    add_matchup(insert, 1200, "water", "ground", 40, 29)
    add_matchup(insert, 1400, "water", "ground", 20, 12)
    add_matchup(insert, 1400, "water", "water", 10, 5)
    add_matchup(insert, 1400, "ground", "water", 20, 8)

    body = client.get(
        "/v1/replays/type-matchups", params={"elo_band": 1400, "type": "Water", "opponent_type": "ground"}
    ).json()

    assert [(row["elo_band"], row["type"], row["opponent_type"], row["win_rate"]) for row in body["data"]] == [
        (1400, "water", "ground", 0.6)
    ]
    assert body["page"]["total"] == 1


def test_type_matchups_list_every_band_in_order(client, insert):
    add_sample(insert)
    add_matchup(insert, 1400, "water", "water", 10, 5)
    add_matchup(insert, 1200, "water", "ground", 40, 29)

    body = client.get("/v1/replays/type-matchups").json()

    assert [(row["elo_band"], row["opponent_type"], row["win_rate"]) for row in body["data"]] == [
        (1200, "ground", 0.725),
        (1400, "water", None),
    ]


def test_leads_put_the_most_common_lead_first_within_each_type(client, insert):
    add_sample(insert)
    for species_id, species, lead_count in ((1, "pelipper", 30), (2, "barraskewda", 50)):
        insert(
            "replay_lead",
            format="gen9monotype",
            report_month=SEPTEMBER,
            elo_band=1200,
            team_type="water",
            species_id=species_id,
            species=species,
            species_name=species.title(),
            lead_count=lead_count,
            team_count=80,
            lead_share=lead_count / 80,
            win_count=lead_count // 2,
            win_rate=0.5,
        )

    body = client.get("/v1/replays/leads", params={"team_type": "water"}).json()

    assert [(row["species"], row["lead_share"]) for row in body["data"]] == [
        ("barraskewda", 0.625),
        ("pelipper", 0.375),
    ]


@pytest.mark.parametrize("params", [{}, {"team_type": "overall"}])
def test_leads_list_every_type_when_the_filter_is_left_out_or_overall(client, insert, params):
    add_sample(insert)
    for species_id, species, team_type in ((1, "pelipper", "water"), (2, "charizard", "fire")):
        insert(
            "replay_lead",
            format="gen9monotype",
            report_month=SEPTEMBER,
            elo_band=1200,
            team_type=team_type,
            species_id=species_id,
            species=species,
            species_name=species.title(),
            lead_count=10,
            team_count=10,
            lead_share=1,
            win_count=5,
            win_rate=0.5,
        )

    body = client.get("/v1/replays/leads", params=params).json()

    assert [row["team_type"] for row in body["data"]] == ["fire", "water"]


def test_move_damage_filters_by_attacker_and_move_by_name(client, insert):
    add_sample(insert)
    species_ids = {"swampert": 1, "garchomp": 2}
    move_ids = {"earthquake": 1, "flipturn": 2}
    hits_by_attack = (("swampert", "earthquake", 40), ("swampert", "flipturn", 25), ("garchomp", "earthquake", 60))
    for species, move, hits in hits_by_attack:
        insert(
            "replay_move_damage",
            format="gen9monotype",
            report_month=SEPTEMBER,
            elo_band=1200,
            species_id=species_ids[species],
            species=species,
            species_name=species.title(),
            move_id=move_ids[move],
            move=move,
            move_name=move.title(),
            hit_count=hits,
            mean_damage_percent=38.5,
            knockout_count=hits // 5,
        )

    by_species = client.get("/v1/replays/move-damage", params={"species": "Swampert"}).json()
    by_move = client.get("/v1/replays/move-damage", params={"move": "Earthquake"}).json()

    assert [row["move"] for row in by_species["data"]] == ["earthquake", "flipturn"]
    assert [row["species"] for row in by_move["data"]] == ["garchomp", "swampert"]


def test_hazard_damage_orders_by_band_type_and_hazard(client, insert):
    add_sample(insert)
    rows = ((1200, "water", "Stealth Rock"), (1000, "water", "Spikes"), (1000, "fire", "Stealth Rock"))
    for elo_band, team_type, hazard in rows:
        insert(
            "replay_hazard_damage",
            format="gen9monotype",
            report_month=SEPTEMBER,
            elo_band=elo_band,
            team_type=team_type,
            hazard=hazard,
            hit_count=100,
            mean_damage_percent=12.5,
            knockout_count=4,
        )

    body = client.get("/v1/replays/hazard-damage").json()

    assert [(row["elo_band"], row["team_type"], row["hazard"]) for row in body["data"]] == [
        (1000, "fire", "Stealth Rock"),
        (1000, "water", "Spikes"),
        (1200, "water", "Stealth Rock"),
    ]
