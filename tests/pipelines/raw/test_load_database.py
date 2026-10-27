"""Runs the raw loaders against real tables built from sql/ (see tests/pipelines/conftest.py)."""

import copy
import json
from datetime import date

import pytest

from pipelines import smogon
from pipelines.raw import chaos, source_file
from pipelines.raw.load import load_file
from tests.pipelines.raw.test_chaos import REPORT

OVERALL = smogon.report_files("chaos", date(2026, 9, 1), [])[0]


def serve(monkeypatch, report: dict) -> None:
    monkeypatch.setattr(source_file.download, "fetch", lambda url: json.dumps(report).encode())


def table_counts(conn) -> dict[str, int]:
    tables = ["source_file", "chaos_report", "chaos_pokemon", "chaos_option", "chaos_counter"]
    return {table: conn.execute(f"SELECT count(*) FROM raw.{table}").fetchone()[0] for table in tables}


def test_load_file_fills_every_table(conn, monkeypatch):
    serve(monkeypatch, REPORT)

    assert load_file(conn, OVERALL, None) == {"pokemon": 1, "options": 9, "counters": 1}
    assert table_counts(conn) == {
        "source_file": 1,
        "chaos_report": 1,
        "chaos_pokemon": 1,
        "chaos_option": 9,
        "chaos_counter": 1,
    }
    assert conn.execute(
        "SELECT o.weight FROM raw.chaos_option o JOIN raw.chaos_pokemon p USING (chaos_pokemon_id)"
        " WHERE p.pokemon = 'Swampert' AND o.category = 'items' AND o.label = 'leftovers'"
    ).fetchone() == (848.989,)


def test_reloading_the_same_file_inserts_nothing(conn, monkeypatch):
    serve(monkeypatch, REPORT)
    load_file(conn, OVERALL, None)

    assert load_file(conn, OVERALL, None) is None
    assert table_counts(conn)["source_file"] == 1


def test_republished_file_is_loaded_again(conn, monkeypatch):
    serve(monkeypatch, REPORT)
    load_file(conn, OVERALL, None)
    republished = copy.deepcopy(REPORT)
    republished["info"]["number of battles"] = 63600
    serve(monkeypatch, republished)

    assert load_file(conn, OVERALL, None) is not None
    assert table_counts(conn)["source_file"] == 2
    assert table_counts(conn)["chaos_pokemon"] == 2


def test_invalid_file_inserts_nothing(conn, monkeypatch):
    invalid = copy.deepcopy(REPORT)
    invalid["data"]["Swampert"].pop("Items")
    serve(monkeypatch, invalid)

    with pytest.raises(chaos.ChaosFormatError, match=OVERALL.url):
        load_file(conn, OVERALL, None)
    assert table_counts(conn)["source_file"] == 0
