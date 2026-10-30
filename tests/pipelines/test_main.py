import subprocess
import urllib.error
from datetime import UTC, date, datetime
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


@pytest.mark.parametrize(
    ("today", "month"),
    [
        (date(2026, 10, 30), date(2026, 9, 1)),
        (date(2026, 10, 1), date(2026, 9, 1)),
        (date(2027, 1, 15), date(2026, 12, 1)),
    ],
)
def test_previous_month(today, month):
    assert cli.previous_month(today) == month


def fake_update_smogon(monkeypatch, missing=(), published=True, load=None, dbt_statuses=(0, 0)):
    """Fakes update_smogon's database, Smogon, load, and dbt calls; returns the calls made, in order."""
    calls = []
    statuses = list(dbt_statuses)

    def exists(url):
        calls.append(("exists", url))
        return published

    def load_smogon(month, families):
        calls.append(("load_smogon", month, families))
        if load:
            load()

    def run(command, check):
        calls.append(("dbt", command[command.index("--select") + 1]))
        return subprocess.CompletedProcess(command, statuses.pop(0))

    monkeypatch.setattr(cli.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(cli.db, "connect", FakeConnection)
    monkeypatch.setattr(cli, "existing_ids", lambda conn, table: {"water": 11})
    monkeypatch.setattr(cli.source_file, "missing_urls", lambda conn, urls: [url for url in urls if url in missing])
    monkeypatch.setattr(cli.download, "exists", exists)
    monkeypatch.setattr(cli, "load_smogon", load_smogon)
    monkeypatch.setattr(cli.subprocess, "run", run)
    return calls


USAGE_1630 = "https://www.smogon.com/stats/2026-09/gen9monotype-1630.txt"


def test_update_smogon_skips_a_loaded_month_without_requests(monkeypatch, capsys):
    calls = fake_update_smogon(monkeypatch)

    cli.update_smogon(date(2026, 10, 30))

    assert calls == []
    assert capsys.readouterr().out == "2026-09 is already loaded\n"


def test_update_smogon_waits_for_smogon_to_publish(monkeypatch, capsys):
    calls = fake_update_smogon(monkeypatch, missing=[USAGE_1630], published=False)

    cli.update_smogon(date(2026, 10, 30))

    assert calls == [("exists", USAGE_1630)]
    assert capsys.readouterr().out == "2026-09 isn't published yet\n"


def test_update_smogon_loads_then_builds_staging_and_api(monkeypatch, capsys):
    calls = fake_update_smogon(monkeypatch, missing=[USAGE_1630])

    cli.update_smogon(date(2026, 10, 30))

    assert calls == [
        ("exists", USAGE_1630),
        ("load_smogon", date(2026, 9, 1), ["chaos", "usage", "leads", "metagame", "matchup_chart"]),
        ("dbt", "staging"),
        ("dbt", "api"),
    ]
    # 2 overall reports for matchup charts, and 4 (overall and water) for each other family.
    assert capsys.readouterr().out == "2026-09: loading 1 of 18 files\n"


def test_update_smogon_skips_dbt_when_the_load_fails(monkeypatch):
    def load():
        raise SystemExit(1)

    calls = fake_update_smogon(monkeypatch, missing=[USAGE_1630], load=load)

    with pytest.raises(SystemExit) as exit_info:
        cli.update_smogon(date(2026, 10, 30))

    assert exit_info.value.code == 1
    assert calls[-1][0] == "load_smogon"


def test_update_smogon_skips_api_when_staging_fails(monkeypatch, capsys):
    calls = fake_update_smogon(monkeypatch, missing=[USAGE_1630], dbt_statuses=(1,))

    with pytest.raises(SystemExit) as exit_info:
        cli.update_smogon(date(2026, 10, 30))

    assert exit_info.value.code == 1
    assert calls[-1] == ("dbt", "staging")
    assert capsys.readouterr().err == (
        "`dbt build --select staging --project-dir transform --profiles-dir transform` failed with status 1\n"
    )


def test_update_smogon_requires_dbt_before_loading(monkeypatch):
    calls = fake_update_smogon(monkeypatch, missing=[USAGE_1630])
    monkeypatch.setattr(cli.shutil, "which", lambda name: None)

    with pytest.raises(RuntimeError, match="dbt is not installed"):
        cli.update_smogon(date(2026, 10, 30))

    assert calls == []


def test_update_smogon_command_uses_todays_utc_date(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "update_smogon", calls.append)
    monkeypatch.setattr("sys.argv", ["pipelines", "update-smogon"])

    cli.main()

    assert calls == [datetime.now(UTC).date()]
