from datetime import UTC, datetime

import pytest

from pipelines import battle_log
from pipelines.battle_log import PreviewPokemon, Side
from pipelines.replays import ReplayFormatError

REPLAY_ID = "gen9monotype-2703725750"
HEADER = """|j|☆jago421
|t:|1792817387
|gametype|singles
|player|p1|jago421|pokemonranger-gen4|1093
|player|p2|MistyMarill|misty|1141
|teamsize|p1|2
|teamsize|p2|2
|gen|9
|tier|[Gen 9] Monotype
|rated|
|rule|Sleep Clause Mod: Limit one foe put to sleep
|rule|Terastal Clause: You cannot Terastallize
|clearpoke
|poke|p1|Gengar, M|
|poke|p1|Urshifu-*, F|
|poke|p2|Tinkaton, F|
|poke|p2|Mimikyu, F|
|teampreview
|
|t:|1792817400
|start
|switch|p1a: Ghostly|Gengar, M|100/100
|switch|p2a: Tinkaton|Tinkaton, F|100/100
|turn|1
|c|☆jago421|gl hf
|
|t:|1792817405
|move|p2a: Tinkaton|Gigaton Hammer|p1a: Ghostly
|-damage|p1a: Ghostly|0 fnt
|faint|p1a: Ghostly
|
|t:|1792817410
|switch|p1a: Fist|Urshifu-Rapid-Strike, F|100/100
|turn|2
"""
ENDING = """|
|t:|1792817652
|win|jago421
|raw|jago421's rating: 1093 &rarr; <strong>1123</strong><br />(+30 for winning)
|raw|MistyMarill's rating: 1141 &rarr; <strong>1113</strong><br />(-28 for losing)
|l|☆MistyMarill
"""


def parse(log: str):
    return battle_log.parse(log, REPLAY_ID)


def test_parse_reads_the_battle_its_players_and_their_teams():
    battle = parse(HEADER + ENDING)

    assert battle.replay_id == REPLAY_ID
    assert battle.rated is True
    assert battle.started_at == datetime.fromtimestamp(1792817387, UTC)
    assert battle.ended_at == datetime.fromtimestamp(1792817652, UTC)
    assert battle.turns == 2
    assert battle.winner == "p1"
    assert battle.ended_by == "knockout"
    assert battle.rules == ("Sleep Clause Mod", "Terastal Clause")
    assert battle.sides == (
        Side("p1", "jago421", 1093, 1123, "win"),
        Side("p2", "MistyMarill", 1141, 1113, "loss"),
    )
    assert battle.team == (
        PreviewPokemon("p1", 1, "Gengar", "Ghostly"),
        PreviewPokemon("p1", 2, "Urshifu-*", "Fist"),
        PreviewPokemon("p2", 1, "Tinkaton", "Tinkaton"),
        PreviewPokemon("p2", 2, "Mimikyu", None),
    )


def test_parse_uses_the_battles_own_rating_change():
    # Another of jago421's battles ended first, so the rating at the start differs from the one just before the update.
    battle = parse(HEADER.replace("pokemonranger-gen4|1093", "pokemonranger-gen4|1080") + ENDING)

    assert battle.sides[0] == Side("p1", "jago421", 1093, 1123, "win")


def test_parse_falls_back_to_the_starting_rating():
    ending = "|\n|t:|1792817652\n|-message|MistyMarill lost due to inactivity.\n|win|jago421\n"

    battle = parse(HEADER + ending)

    assert battle.ended_by == "inactivity"
    assert battle.sides == (
        Side("p1", "jago421", 1093, None, "win"),
        Side("p2", "MistyMarill", 1141, None, "loss"),
    )


def test_parse_reads_a_forfeit():
    ending = "|\n|t:|1792817652\n|-message|jago421 forfeited.\n|win|MistyMarill\n"

    battle = parse(HEADER + ending)

    assert (battle.winner, battle.ended_by) == ("p2", "forfeit")
    assert [side.result for side in battle.sides] == ["loss", "win"]


def test_parse_reads_a_tie():
    battle = parse(HEADER + "|\n|t:|1792817652\n|tie\n")

    assert (battle.winner, battle.ended_by) == (None, "tie")
    assert [side.result for side in battle.sides] == ["tie", "tie"]


def test_a_tournament_battle_is_not_rated():
    battle = parse(HEADER.replace("|rated|\n", "|rated|Tournament battle\n") + ENDING)

    assert battle.rated is False


def test_an_unrated_battle_has_no_ratings():
    header = HEADER.replace("|rated|\n", "").replace("-gen4|1093", "-gen4|").replace("misty|1141", "misty|")

    battle = parse(header + "|\n|t:|1792817652\n|win|jago421\n")

    assert battle.rated is False
    assert [(side.elo_before, side.elo_after) for side in battle.sides] == [(None, None), (None, None)]


def test_a_battle_that_ends_at_team_preview():
    log = HEADER[: HEADER.index("|start")] + "|-message|MistyMarill forfeited.\n|win|jago421\n"

    battle = parse(log)

    assert (battle.turns, battle.ended_by) == (0, "forfeit")
    assert all(pokemon.nickname is None for pokemon in battle.team if pokemon.side == "p2")


def test_a_leaving_player_keeps_their_name():
    battle = parse(HEADER + "|player|p2|\n" + ENDING)

    assert battle.sides[1].player == "MistyMarill"


@pytest.mark.parametrize(
    ("previewed", "entered"),
    [("Terapagos", "Terapagos-Terastal"), ("Mimikyu", "Mimikyu-Busted"), ("Urshifu-*", "Urshifu")],
)
def test_nicknames_match_pokemon_that_enter_in_another_form(previewed, entered):
    # The second previewed Pokémon becomes Gengar, so the team has only one Pokémon of each species.
    log = HEADER.replace("|poke|p1|Urshifu-*, F|", "|poke|p1|Gengar, M|").replace(
        "|switch|p1a: Fist|Urshifu-Rapid-Strike, F|", "|switch|p1a: Fist|Gengar, M|"
    )
    log = log.replace("|poke|p1|Gengar, M|", f"|poke|p1|{previewed}|", 1).replace(
        "|switch|p1a: Ghostly|Gengar, M|", f"|switch|p1a: Ghostly|{entered}|"
    )

    battle = parse(log + ENDING)

    assert battle.team[0] == PreviewPokemon("p1", 1, previewed, "Ghostly")


def test_a_different_species_is_not_taken_for_a_form():
    # Porygon-Z is its own species, so it can share a team with Porygon; it isn't a form of it.
    log = HEADER.replace("|poke|p1|Gengar, M|", "|poke|p1|Porygon|").replace(
        "|poke|p1|Urshifu-*, F|", "|poke|p1|Porygon-Z|"
    )
    log = log.replace("|switch|p1a: Ghostly|Gengar, M|", "|switch|p1a: Zed|Porygon-Z|").replace(
        "|switch|p1a: Fist|Urshifu-Rapid-Strike, F|", "|switch|p1a: Pory|Porygon|"
    )
    log = log.replace("p1a: Ghostly", "p1a: Zed")

    battle = parse(log + ENDING)

    assert [(pokemon.species, pokemon.nickname) for pokemon in battle.team[:2]] == [
        ("Porygon", "Pory"),
        ("Porygon-Z", "Zed"),
    ]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (("|turn|2\n", "|turn|2\n|-newline|p1\n"), "unknown line type '-newline'"),
        (("|gametype|singles", "|gametype|doubles"), "not singles"),
        (("|gen|9", "|gen|8"), "not 9"),
        (("|player|p2|MistyMarill|misty|1141\n", ""), "names players"),
        (("|poke|p2|Mimikyu, F|\n", ""), "previews 1 Pokémon for p2"),
        (("|turn|2", "|turn|two"), "turn line"),
    ],
)
def test_parse_rejects_unexpected_logs(change, message):
    with pytest.raises(ReplayFormatError, match=message):
        parse(HEADER.replace(*change) + ENDING)


@pytest.mark.parametrize(
    ("ending", "message"),
    [
        ("|win|jago421\n|tie\n", "neither a single winner nor a tie"),
        ("|t:|1792817652\n", "neither a single winner nor a tie"),
        ("|win|Somebody\n", "who isn't a player"),
    ],
)
def test_parse_rejects_unclear_results(ending, message):
    with pytest.raises(ReplayFormatError, match=message):
        parse(HEADER + ending)
