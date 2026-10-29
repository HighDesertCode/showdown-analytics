import urllib.error
from datetime import date
from email.message import Message

import pytest

from pipelines import __main__ as cli


class FakeConnection:
    def __init__(self):
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, query):
        return self

    def fetchone(self):
        return ("showdown-analyst", "showdown-database", True)

    def commit(self):
        self.commits += 1


def test_check_connection_reports_target(monkeypatch, capsys):
    monkeypatch.setattr(cli.db, "connect", FakeConnection)
    monkeypatch.setattr("sys.argv", ["pipelines", "check-connection"])

    cli.main()

    assert capsys.readouterr().out == "Connected to showdown-database as showdown-analyst (SSL: True)\n"


def test_unknown_command_exits(monkeypatch):
    monkeypatch.setattr("sys.argv", ["pipelines", "nope"])

    with pytest.raises(SystemExit) as exit_info:
        cli.main()

    assert exit_info.value.code == 2


def test_load_smogon_rejects_invalid_month(monkeypatch):
    monkeypatch.setattr("sys.argv", ["pipelines", "load-smogon", "September"])

    with pytest.raises(SystemExit) as exit_info:
        cli.main()

    assert exit_info.value.code == 2


@pytest.mark.parametrize(
    ("arguments", "families"),
    [
        ([], ["chaos", "usage", "leads", "metagame", "matchup_chart"]),
        (["--family", "usage"], ["usage"]),
        (["--family", "usage", "--family", "chaos"], ["usage", "chaos"]),
    ],
)
def test_load_smogon_families(monkeypatch, arguments, families):
    calls = []
    monkeypatch.setattr(cli, "load_smogon", lambda month, families: calls.append((month, families)))
    monkeypatch.setattr("sys.argv", ["pipelines", "load-smogon", "2026-09", *arguments])

    cli.main()

    assert calls == [(date(2026, 9, 1), families)]


def test_load_smogon_rejects_unknown_family(monkeypatch):
    monkeypatch.setattr("sys.argv", ["pipelines", "load-smogon", "2026-09", "--family", "moveset"])

    with pytest.raises(SystemExit) as exit_info:
        cli.main()

    assert exit_info.value.code == 2


def test_load_smogon_requires_reference_types(monkeypatch):
    monkeypatch.setattr(cli.db, "connect", FakeConnection)
    monkeypatch.setattr(cli, "existing_ids", lambda conn, table: {})

    with pytest.raises(RuntimeError, match="load-reference"):
        cli.load_smogon(date(2026, 9, 1), ["chaos"])


def test_load_smogon_continues_past_failed_downloads(monkeypatch, capsys):
    conn = FakeConnection()
    monkeypatch.setattr(cli.db, "connect", lambda: conn)
    monkeypatch.setattr(cli, "existing_ids", lambda conn, table: {"water": 11})
    loaded = []

    def load_file(conn, file, team_type_id):
        if file.baseline == 1630:
            raise urllib.error.HTTPError(file.url, 404, "Not Found", Message(), None)
        loaded.append(file.url)
        return {"matchup_chart_cell": 324}

    monkeypatch.setattr(cli, "load_file", load_file)

    with pytest.raises(SystemExit) as exit_info:
        cli.load_smogon(date(2026, 9, 1), ["matchup_chart"])

    assert exit_info.value.code == 1
    assert loaded == ["https://www.smogon.com/stats/2026-09/monotype/matchupcharts/gen9monotype-matchup_chart-1760.txt"]
    assert conn.commits == 1
    output = capsys.readouterr()
    assert "1630  failed (HTTP Error 404: Not Found)" in output.out
    assert output.err == (
        "\n1 of 2 files failed to download; rerun to load them:\n"
        "  https://www.smogon.com/stats/2026-09/monotype/matchupcharts/gen9monotype-matchup_chart-1630.txt: "
        "HTTP Error 404: Not Found\n"
    )
