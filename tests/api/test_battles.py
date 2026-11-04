from datetime import UTC, date, datetime, timedelta

import pytest

SEPTEMBER = date(2026, 9, 1)
START = datetime(2026, 9, 10, 18, 0, tzinfo=UTC)


def add_battle(insert, number, sides, rated=True, month=SEPTEMBER, started_at=None):
    """A battle and its two sides, each a (player, team_type, elo_band, result) tuple for p1 then p2."""
    replay_id = f"gen9monotype-{number}"
    started = started_at or START + timedelta(hours=number)
    insert(
        "replay_battle",
        replay_id=replay_id,
        format="gen9monotype",
        report_month=month,
        replay_url=f"https://replay.pokemonshowdown.com/{replay_id}",
        rated=rated,
        started_at=started,
        ended_at=started + timedelta(minutes=12),
        turns=24,
        winner="p1",
        ended_by="knockout",
        rules=["Same Type Clause", "Species Clause"],
        uploaded_at=started + timedelta(minutes=13),
        parsed_at=started + timedelta(hours=1),
    )
    for side, (player, team_type, elo_band, result) in zip(("p1", "p2"), sides, strict=True):
        insert(
            "replay_battle_side",
            replay_id=replay_id,
            side=side,
            player=player,
            player_id=player.lower().replace(" ", ""),
            elo_before=elo_band + 50 if elo_band else None,
            elo_after=elo_band + 60 if elo_band else None,
            elo_band=elo_band,
            result=result,
            team_type=team_type,
        )
    return replay_id


@pytest.fixture
def battles(insert):
    """Three battles: Some Player on Water beats a Fire team, then loses with Fire, then an unrated one."""
    return [
        add_battle(insert, 1, [("Some Player", "water", 1400, "win"), ("Rival", "fire", 1200, "loss")]),
        add_battle(insert, 2, [("Rival", "water", 1200, "win"), ("Some Player", "fire", 1400, "loss")]),
        add_battle(insert, 3, [("Friend", "ghost", None, "win"), ("Some Player", None, None, "loss")], rated=False),
    ]


def search(client, **params):
    return client.get("/v1/battles", params=params).json()


def replay_ids(body):
    return [battle["replay_id"] for battle in body["data"]]


def test_search_lists_battles_newest_first_with_both_sides(client, battles):
    body = search(client)

    assert body["scope"]["source"] == "replay_battles"
    assert replay_ids(body) == ["gen9monotype-3", "gen9monotype-2", "gen9monotype-1"]
    assert [side["player"] for side in body["data"][2]["sides"]] == ["Some Player", "Rival"]
    assert body["data"][2]["replay_url"] == "https://replay.pokemonshowdown.com/gen9monotype-1"
    assert body["page"]["total"] == 3


def test_search_matches_a_player_however_the_name_is_written(client, battles):
    body = search(client, player="SOME player")

    assert body["scope"]["player"] == "someplayer"
    assert replay_ids(body) == ["gen9monotype-3", "gen9monotype-2", "gen9monotype-1"]


def test_search_applies_side_filters_to_the_same_side(client, battles):
    # Some Player faced a Water team in battle 2, but played Water only in battle 1.
    body = search(client, player="someplayer", team_type="water")

    assert replay_ids(body) == ["gen9monotype-1"]


def test_search_filters_by_rated_and_elo_band(client, battles):
    assert replay_ids(search(client, rated=False)) == ["gen9monotype-3"]
    assert replay_ids(search(client, elo_band=1200)) == ["gen9monotype-2", "gen9monotype-1"]


def test_search_filters_by_month(client, insert, battles):
    sides = [("Some Player", "water", 1400, "win"), ("Rival", "fire", 1200, "loss")]
    add_battle(insert, 4, sides, month=date(2026, 8, 1))

    assert replay_ids(search(client, month="2026-08")) == ["gen9monotype-4"]


def test_search_pages(client, battles):
    body = search(client, limit=1, offset=1)

    assert replay_ids(body) == ["gen9monotype-2"]
    assert body["page"] == {"limit": 1, "offset": 1, "total": 3}


def test_search_treats_overall_as_every_team_type(client, battles):
    body = search(client, team_type="overall")

    assert body["scope"]["team_type"] is None
    assert len(body["data"]) == 3


def test_search_with_no_matches_has_an_empty_page(client, battles):
    body = search(client, player="nobody")

    assert body["data"] == []
    assert body["page"] == {"limit": 50, "offset": 0, "total": 0}


def test_search_rejects_a_player_with_no_letters_or_digits(client, battles):
    response = client.get("/v1/battles", params={"player": "!!"})

    assert response.status_code == 422
    assert response.json() == {"detail": "'!!' isn't a player name"}


def test_battle_has_its_rules_and_both_previewed_teams(client, insert, battles):
    insert("species", species_id=1, species="urshifu", species_name="Urshifu")
    insert("species", species_id=2, species="pelipper", species_name="Pelipper")
    for side, slot, previewed, species_id, hidden in (("p1", 1, "Pelipper", 2, False), ("p2", 1, "Urshifu-*", 1, True)):
        insert(
            "replay_battle_pokemon",
            replay_id="gen9monotype-1",
            side=side,
            slot=slot,
            previewed_species=previewed,
            species_id=species_id,
            form_hidden=hidden,
            parsed_at=START,
        )

    body = client.get("/v1/battles/gen9monotype-1").json()

    battle = body["data"]
    assert body["scope"]["month"] == "2026-09"
    assert battle["rules"] == ["Same Type Clause", "Species Clause"]
    assert [side["team_type"] for side in battle["sides"]] == ["water", "fire"]
    assert battle["sides"][1]["team"] == [
        {
            "slot": 1,
            "previewed_species": "Urshifu-*",
            "species": "urshifu",
            "species_name": "Urshifu",
            "form_hidden": True,
            "nickname": None,
        }
    ]


def test_battle_explains_a_missing_replay(client, battles):
    response = client.get("/v1/battles/gen9monotype-999")

    assert response.status_code == 404
    assert response.json() == {"detail": "No parsed replay gen9monotype-999"}


def add_event(insert, seq, turn, event, **values):
    insert(
        "replay_battle_event",
        replay_id="gen9monotype-1",
        seq=seq,
        turn=turn,
        event=event,
        source_inferred=values.pop("source_inferred", False),
        parsed_at=START,
        **values,
    )


def test_events_follow_the_battle_in_order_with_each_forms_species(client, insert, battles):
    insert("species", species_id=3, species="urshifurapidstrike", species_name="Urshifu-Rapid-Strike")
    insert("species", species_id=2, species="pelipper", species_name="Pelipper")
    add_event(insert, 1, 0, "switch", side="p2", pokemon="Urshifu-*", species_id=3, detail="Urshifu-Rapid-Strike")
    add_event(
        insert,
        2,
        1,
        "move",
        side="p2",
        pokemon="Urshifu-*",
        species_id=3,
        detail="Surging Strikes",
        target_side="p1",
        target_pokemon="Pelipper",
        target_species_id=2,
    )
    add_event(
        insert,
        3,
        1,
        "damage",
        side="p1",
        pokemon="Pelipper",
        species_id=2,
        damage_percent=45,
        hp_after_percent=55,
        caused_by_seq=2,
        source_inferred=True,
    )

    body = client.get("/v1/battles/gen9monotype-1/events").json()

    events = body["data"]
    assert [event["seq"] for event in events] == [1, 2, 3]
    assert events[1]["species_name"] == "Urshifu-Rapid-Strike"
    assert events[1]["target_species"] == "pelipper"
    assert (events[2]["damage_percent"], events[2]["caused_by_seq"], events[2]["source_inferred"]) == (45, 2, True)
    assert body["page"]["total"] == 3


def test_events_filter_by_turn_and_page(client, insert, battles):
    for seq, turn in ((1, 0), (2, 1), (3, 1), (4, 2)):
        add_event(insert, seq, turn, "move")

    by_turn = client.get("/v1/battles/gen9monotype-1/events", params={"turn": 1}).json()
    paged = client.get("/v1/battles/gen9monotype-1/events", params={"limit": 2, "offset": 2}).json()

    assert [event["seq"] for event in by_turn["data"]] == [2, 3]
    assert by_turn["page"]["total"] == 2
    assert [event["seq"] for event in paged["data"]] == [3, 4]
    assert paged["page"]["total"] == 4


def test_events_explain_a_missing_replay(client, battles):
    assert client.get("/v1/battles/gen9monotype-999/events").status_code == 404
