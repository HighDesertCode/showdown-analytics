import copy
import json
from datetime import date
from typing import Any

import pytest

from pipelines import smogon
from pipelines.raw import chaos
from pipelines.raw.common import ReportFormatError

OVERALL, WATER = smogon.report_files("chaos", date(2026, 9, 1), ["water"])[:2]

# A trimmed version of a real chaos report, typed loosely like the parsed JSON it stands in for.
REPORT: dict[str, Any] = {
    "info": {
        "metagame": "gen9monotype",
        "cutoff": 1630,
        "cutoff deviation": 0,
        "team type": None,
        "number of battles": 63572,
    },
    "data": {
        "Swampert": {
            "Raw count": 4603,
            "usage": 0.6506545,
            "Viability Ceiling": [571, 88, 83, 66],
            "Abilities": {"torrent": 1209.08, "damp": 220.31},
            "Items": {"leftovers": 848.989},
            "Moves": {"stealthrock": 1344.34, "earthquake": 1425.51},
            "Spreads": {"Relaxed:252/0/252/0/4/0": 300.5},
            "Teammates": {"Alomomola": 147.0},
            "Tera Types": {"nothing": 1429.39},
            "Happiness": {"255": 1429.39},
            "Checks and Counters": {"Ogerpon-Wellspring": {"n": 43.2, "p": 0.35, "d": 0.07}},
        }
    },
}


def encode(report: dict) -> bytes:
    return json.dumps(report).encode()


def test_parse_builds_rows():
    report = chaos.parse(encode(REPORT), OVERALL)

    assert report.info == ("gen9monotype", 1630, 0, None, 63572)
    assert report.pokemon == [("Swampert", 4603, 0.6506545, 571, 88, 83, 66)]
    assert ("Swampert", "items", "leftovers", 848.989) in report.options
    assert ("Swampert", "spreads", "Relaxed:252/0/252/0/4/0", 300.5) in report.options
    assert len(report.options) == 9
    assert report.counters == [("Swampert", "Ogerpon-Wellspring", 43.2, 0.35, 0.07)]


def test_parse_accepts_team_type_report():
    report = copy.deepcopy(REPORT)
    report["info"]["team type"] = "monowater"

    assert chaos.parse(encode(report), WATER).info[3] == "monowater"


def test_parse_stores_integer_weights_as_floats():
    report = copy.deepcopy(REPORT)
    report["data"]["Swampert"]["Items"] = {"leftovers": 12}

    assert ("Swampert", "items", "leftovers", 12.0) in chaos.parse(encode(report), OVERALL).options


def broken(change) -> dict:
    report = copy.deepcopy(REPORT)
    change(report)
    return report


@pytest.mark.parametrize(
    ("report", "message"),
    [
        (broken(lambda r: r["data"]["Swampert"].pop("Items")), "missing \\['Items'\\]"),
        (broken(lambda r: r["data"]["Swampert"].update({"Natures": {}})), "unexpected \\['Natures'\\]"),
        (broken(lambda r: r["data"]["Swampert"].update({"Viability Ceiling": [571, 88, 83]})), "4 values"),
        (broken(lambda r: r["data"]["Swampert"].update({"Raw count": "4603"})), "expected an integer"),
        (broken(lambda r: r["data"]["Swampert"]["Items"].update({"leftovers": True})), "expected a number"),
        (broken(lambda r: r["data"]["Swampert"]["Checks and Counters"]["Ogerpon-Wellspring"].pop("d")), "missing"),
        (broken(lambda r: r["info"].update({"cutoff": 1760})), "info: expected"),
        (broken(lambda r: r["info"].update({"team type": "monowater"})), "info: expected"),
        (broken(lambda r: r.update({"data": []})), "expected an object"),
    ],
)
def test_parse_rejects_unexpected_shapes(report, message):
    with pytest.raises(ReportFormatError, match=message):
        chaos.parse(encode(report), OVERALL)
