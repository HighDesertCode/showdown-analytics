import urllib.error
from datetime import date
from email.message import Message

import pytest

from pipelines import __main__ as cli
from pipelines.raw.common import ReportFormatError


class FakeConnection:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

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

    def rollback(self):
        self.rollbacks += 1


class FakeIngestionRun:
    """Records the calls load_smogon makes to pipelines.raw.ingestion_run."""

    def __init__(self):
        self.calls = []

    def start(self, conn, month, families):
        self.calls.append(("start", month, families))
        return 7

    def record_file(self, conn, run_id, outcome):
        self.calls.append(("record_file", run_id, outcome))

    def finish(self, conn, run_id, status, error=None):
        self.calls.append(("finish", run_id, status, error, conn.rollbacks))


def fake_load_smogon(monkeypatch, load_file):
    """Runs load_smogon on the two matchup charts with a fake connection, loader, and run log."""
    conn = FakeConnection()
    run = FakeIngestionRun()
    monkeypatch.setattr(cli.db, "connect", lambda: conn)
    monkeypatch.setattr(cli, "existing_ids", lambda conn, table: {"water": 11})
    monkeypatch.setattr(cli, "load_file", load_file)
    monkeypatch.setattr(cli, "ingestion_run", run)
    return conn, run


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


def test_load_smogon_records_a_succeeded_run(monkeypatch):
    def load_file(conn, file, team_type_id):
        return None if file.baseline == 1630 else {"matchup_chart_cell": 324}

    conn, run = fake_load_smogon(monkeypatch, load_file)

    cli.load_smogon(date(2026, 9, 1), ["matchup_chart"])

    assert run.calls == [
        ("start", date(2026, 9, 1), ["matchup_chart"]),
        ("record_file", 7, "skipped"),
        ("record_file", 7, "loaded"),
        ("finish", 7, "succeeded", None, 0),
    ]
    assert conn.commits == 4


def test_load_smogon_continues_past_failed_downloads(monkeypatch, capsys):
    loaded = []

    def load_file(conn, file, team_type_id):
        if file.baseline == 1630:
            raise urllib.error.HTTPError(file.url, 404, "Not Found", Message(), None)
        loaded.append(file.url)
        return {"matchup_chart_cell": 324}

    conn, run = fake_load_smogon(monkeypatch, load_file)

    with pytest.raises(SystemExit) as exit_info:
        cli.load_smogon(date(2026, 9, 1), ["matchup_chart"])

    assert exit_info.value.code == 1
    assert loaded == ["https://www.smogon.com/stats/2026-09/monotype/matchupcharts/gen9monotype-matchup_chart-1760.txt"]
    assert run.calls[1:] == [
        ("record_file", 7, "failed"),
        ("record_file", 7, "loaded"),
        ("finish", 7, "partial", None, 0),
    ]
    assert conn.commits == 4
    output = capsys.readouterr()
    assert "1630  failed (HTTP Error 404: Not Found)" in output.out
    assert output.err == (
        "\n1 of 2 files failed to download; rerun to load them:\n"
        "  https://www.smogon.com/stats/2026-09/monotype/matchupcharts/gen9monotype-matchup_chart-1630.txt: "
        "HTTP Error 404: Not Found\n"
    )


def test_load_smogon_records_a_failed_run_after_rolling_back(monkeypatch):
    def load_file(conn, file, team_type_id):
        raise ReportFormatError(f"{file.url}: unexpected header")

    conn, run = fake_load_smogon(monkeypatch, load_file)

    with pytest.raises(ReportFormatError):
        cli.load_smogon(date(2026, 9, 1), ["matchup_chart"])

    url = "https://www.smogon.com/stats/2026-09/monotype/matchupcharts/gen9monotype-matchup_chart-1630.txt"
    # The rollback count of 1 shows the failed file's work was discarded before the result was recorded.
    assert run.calls[1:] == [("finish", 7, "failed", f"ReportFormatError: {url}: unexpected header", 1)]
    assert conn.commits == 2
