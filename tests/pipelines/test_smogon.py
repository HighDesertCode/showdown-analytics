from datetime import date

import pytest

from pipelines import smogon

SEPTEMBER = date(2026, 9, 1)


def test_parse_month():
    assert smogon.parse_month("2026-09") == SEPTEMBER


@pytest.mark.parametrize("text", ["2026-9", "2026-13", "September", "2026-09-01"])
def test_parse_month_rejects_invalid(text):
    with pytest.raises(ValueError):
        smogon.parse_month(text)


def test_url_overall():
    assert smogon.url("chaos", SEPTEMBER, 1630) == "https://www.smogon.com/stats/2026-09/chaos/gen9monotype-1630.json"


def test_url_team_type():
    assert (
        smogon.url("chaos", SEPTEMBER, 1630, "water")
        == "https://www.smogon.com/stats/2026-09/monotype/chaos/gen9monotype-monowater-1630.json"
    )


def test_report_files_cover_every_scope_and_baseline():
    files = smogon.report_files("chaos", SEPTEMBER, ["water", "fire"])

    assert [(file.baseline, file.team_type) for file in files] == [
        (1630, None),
        (1630, "water"),
        (1630, "fire"),
        (1760, None),
        (1760, "water"),
        (1760, "fire"),
    ]
    assert files[1] == smogon.ReportFile(
        family="chaos",
        format="gen9monotype",
        report_month=SEPTEMBER,
        baseline=1630,
        team_type="water",
        url="https://www.smogon.com/stats/2026-09/monotype/chaos/gen9monotype-monowater-1630.json",
    )


def test_usage_urls():
    assert smogon.url("usage", SEPTEMBER, 1630) == "https://www.smogon.com/stats/2026-09/gen9monotype-1630.txt"
    assert (
        smogon.url("usage", SEPTEMBER, 1760, "water")
        == "https://www.smogon.com/stats/2026-09/monotype/gen9monotype-monowater-1760.txt"
    )


def test_leads_urls():
    assert smogon.url("leads", SEPTEMBER, 1630) == "https://www.smogon.com/stats/2026-09/leads/gen9monotype-1630.txt"
    assert (
        smogon.url("leads", SEPTEMBER, 1760, "water")
        == "https://www.smogon.com/stats/2026-09/monotype/leads/gen9monotype-monowater-1760.txt"
    )


def test_metagame_urls():
    assert (
        smogon.url("metagame", SEPTEMBER, 1630) == "https://www.smogon.com/stats/2026-09/metagame/gen9monotype-1630.txt"
    )
    assert (
        smogon.url("metagame", SEPTEMBER, 1760, "water")
        == "https://www.smogon.com/stats/2026-09/monotype/metagame/gen9monotype-monowater-1760.txt"
    )
