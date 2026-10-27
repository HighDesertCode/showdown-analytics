"""Runs the raw loaders against real tables built from sql/ (see tests/pipelines/conftest.py)."""

import copy
import json
from datetime import date
from decimal import Decimal

import pytest

from pipelines import smogon
from pipelines.raw import source_file
from pipelines.raw.common import ReportFormatError
from pipelines.raw.load import load_file
from tests.pipelines.raw.test_chaos import REPORT
from tests.pipelines.raw.test_usage import REPORT as USAGE_REPORT

OVERALL = smogon.report_files("chaos", date(2026, 9, 1), [])[0]
USAGE_OVERALL = smogon.report_files("usage", date(2026, 9, 1), [])[0]


def serve(monkeypatch, report: dict) -> None:
    monkeypatch.setattr(source_file.download, "fetch", lambda url: json.dumps(report).encode())


def table_counts(conn) -> dict[str, int]:
    tables = ["source_file", "chaos_report", "chaos_pokemon", "chaos_option", "chaos_counter"]
    tables += ["usage_report", "usage_pokemon"]
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
        "usage_report": 0,
        "usage_pokemon": 0,
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

    with pytest.raises(ReportFormatError, match=OVERALL.url):
        load_file(conn, OVERALL, None)
    assert table_counts(conn)["source_file"] == 0


def test_load_file_loads_a_usage_report(conn, monkeypatch):
    monkeypatch.setattr(source_file.download, "fetch", lambda url: USAGE_REPORT.encode())

    assert load_file(conn, USAGE_OVERALL, None) == {"pokemon": 2}
    assert conn.execute("SELECT battle_count, avg_team_weight FROM raw.usage_report").fetchone() == (
        63572,
        Decimal("0.192"),
    )
    assert conn.execute(
        "SELECT rank, usage_percent, real_count FROM raw.usage_pokemon WHERE pokemon = 'Ogerpon-Hearthflame'"
    ).fetchone() == (46, Decimal("4.73609"), 5412)
