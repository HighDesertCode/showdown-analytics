import pytest

from pipelines.reference import move

NO_STAGES = (None,) * 7


def stages(changes: dict) -> tuple:
    return tuple(changes.get(stat) for stat in move.BOOST_STATS)


def test_rows_map_type_and_treat_true_accuracy_as_null():
    moves = {
        "swift": {
            "num": 129,
            "name": "Swift",
            "type": "Normal",
            "category": "Special",
            "basePower": 60,
            "accuracy": True,
            "pp": 20,
            "priority": 0,
            "target": "allAdjacentFoes",
        },
    }
    move_text = {"swift": {"shortDesc": "This move does not check accuracy. Hits foes."}}

    assert move.rows(moves, move_text, {"normal": 7}) == [
        (
            "swift",
            "Swift",
            129,
            7,
            "Special",
            60,
            None,
            20,
            0,
            "allAdjacentFoes",
            "This move does not check accuracy. Hits foes.",
            None,
        ),
    ]


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        pytest.param(
            {
                "target": "normal",
                "secondaries": [{"chance": 10, "status": "brn"}, {"chance": 10, "volatileStatus": "flinch"}],
            },
            [
                (True, 10, "target", "brn", None, None, *NO_STAGES),
                (True, 10, "target", None, "flinch", None, *NO_STAGES),
            ],
            id="fire-fang-two-secondaries",
        ),
        pytest.param(
            {"target": "normal", "self": {"boosts": {"def": -1, "spd": -1}}},
            [(False, 100, "self", None, None, None, *stages({"def": -1, "spd": -1}))],
            id="close-combat-guaranteed-self-drop",
        ),
        pytest.param(
            {"target": "self", "boosts": {"atk": 2}},
            [(False, 100, "self", None, None, None, *stages({"atk": 2}))],
            id="swords-dance-self-target",
        ),
        pytest.param(
            {"target": "foeSide", "sideCondition": "stealthrock"},
            [(False, 100, "target", None, None, "stealthrock", *NO_STAGES)],
            id="stealth-rock-hazard",
        ),
        pytest.param(
            {"target": "all", "weather": "RainDance"},
            [(False, 100, "field", None, None, "raindance", *NO_STAGES)],
            id="rain-dance-normalized-field",
        ),
        pytest.param(
            {"target": "normal", "secondary": {"chance": 100, "self": {"boosts": {"atk": 1}}}},
            [(True, 100, "self", None, None, None, *stages({"atk": 1}))],
            id="power-up-punch-secondary-self",
        ),
        pytest.param(
            {"target": "allAdjacentFoes", "self": {"chance": 50, "boosts": {"def": 2}}},
            [(True, 50, "self", None, None, None, *stages({"def": 2}))],
            id="diamond-storm-chance-self",
        ),
        pytest.param(
            {"target": "normal", "secondary": {"chance": 20}},
            [(True, 20, "target", None, None, None, *NO_STAGES)],
            id="tri-attack-chance-only",
        ),
        pytest.param({"target": "normal", "self": {}}, [], id="no-effects"),
    ],
)
def test_effects(data, expected):
    assert move.effects(data) == expected


def test_effect_rows_number_effects_per_move():
    moves = {
        "firefang": {
            "target": "normal",
            "secondaries": [{"chance": 10, "status": "brn"}, {"chance": 10, "volatileStatus": "flinch"}],
        }
    }

    assert [row[:2] for row in move.effect_rows(moves, {"firefang": 5})] == [(5, 1), (5, 2)]
