"""Validates Smogon's chaos JSON reports and turns them into rows for the raw.chaos_* tables.

Validation is strict: any missing, extra, or wrongly typed key raises ChaosFormatError, so a change
in Smogon's format stops the load instead of storing partial or misread data.
"""

import json
from dataclasses import dataclass
from typing import Any

from pipelines.smogon import ReportFile

INFO_KEYS = {"metagame", "cutoff", "cutoff deviation", "team type", "number of battles"}
POKEMON_KEYS = {
    "Raw count",
    "usage",
    "Viability Ceiling",
    "Abilities",
    "Items",
    "Moves",
    "Spreads",
    "Teammates",
    "Tera Types",
    "Happiness",
    "Checks and Counters",
}
# Smogon's option keys and the category each is stored under in raw.chaos_option.
OPTION_CATEGORIES = {
    "Abilities": "abilities",
    "Items": "items",
    "Moves": "moves",
    "Spreads": "spreads",
    "Teammates": "teammates",
    "Tera Types": "tera_types",
    "Happiness": "happiness",
}
COUNTER_KEYS = {"n", "p", "d"}


class ChaosFormatError(ValueError):
    pass


@dataclass(frozen=True)
class ChaosReport:
    info: tuple  # metagame, cutoff, cutoff_deviation, team_type, battle_count
    pokemon: list[tuple]  # pokemon, raw_count, usage, and the four viability values
    options: list[tuple]  # pokemon, category, label, weight
    counters: list[tuple]  # pokemon, opponent, n, p, d


def parse(content: bytes, file: ReportFile) -> ChaosReport:
    document = json.loads(content)
    check_keys(document, {"info", "data"}, "file")
    info = info_row(document["info"], file)
    if not isinstance(document["data"], dict):
        raise ChaosFormatError("data: expected an object")

    pokemon, options, counters = [], [], []
    for name, stats in document["data"].items():
        where = f"data[{name!r}]"
        check_keys(stats, POKEMON_KEYS, where)
        viability = stats["Viability Ceiling"]
        if not (isinstance(viability, list) and len(viability) == 4):
            raise ChaosFormatError(f"{where}['Viability Ceiling']: expected 4 values")
        pokemon.append(
            (
                name,
                integer(stats["Raw count"], f"{where}['Raw count']"),
                number(stats["usage"], f"{where}['usage']"),
                *(integer(value, f"{where}['Viability Ceiling']") for value in viability),
            )
        )
        for key, category in OPTION_CATEGORIES.items():
            for label, weight in mapping(stats[key], f"{where}[{key!r}]").items():
                options.append((name, category, label, number(weight, f"{where}[{key!r}][{label!r}]")))
        for opponent, values in mapping(stats["Checks and Counters"], f"{where}['Checks and Counters']").items():
            counter_where = f"{where}['Checks and Counters'][{opponent!r}]"
            check_keys(values, COUNTER_KEYS, counter_where)
            counters.append((name, opponent, *(number(values[key], counter_where) for key in ("n", "p", "d"))))
    return ChaosReport(info, pokemon, options, counters)


def info_row(info: Any, file: ReportFile) -> tuple:
    """Validates the info block, including that it describes the file we asked for."""
    check_keys(info, INFO_KEYS, "info")
    expected_team_type = None if file.team_type is None else f"mono{file.team_type}"
    actual = {"metagame": info["metagame"], "cutoff": info["cutoff"], "team type": info["team type"]}
    expected = {"metagame": file.format, "cutoff": file.baseline, "team type": expected_team_type}
    if actual != expected:
        raise ChaosFormatError(f"info: expected {expected}, got {actual}")
    return (
        info["metagame"],
        info["cutoff"],
        integer(info["cutoff deviation"], "info['cutoff deviation']"),
        info["team type"],
        integer(info["number of battles"], "info['number of battles']"),
    )


def check_keys(value: Any, expected: set[str], where: str) -> None:
    keys = set(mapping(value, where))
    if keys != expected:
        raise ChaosFormatError(f"{where}: missing {sorted(expected - keys)}, unexpected {sorted(keys - expected)}")


def mapping(value: Any, where: str) -> dict:
    if not isinstance(value, dict):
        raise ChaosFormatError(f"{where}: expected an object")
    return value


# bool is a subclass of int in Python, so both checks exclude it explicitly.
def integer(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ChaosFormatError(f"{where}: expected an integer, got {value!r}")
    return value


def number(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ChaosFormatError(f"{where}: expected a number, got {value!r}")
    return float(value)
