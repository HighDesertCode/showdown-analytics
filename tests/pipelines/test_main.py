import subprocess
import urllib.error
from datetime import UTC, date, datetime
from email.message import Message

import pytest

from pipelines import __main__ as cli
from pipelines.raw.common import ReportFormatError
from pipelines.replays import ReplayFormatError, SearchResult


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


class FakeReplayCollectionRun:
    """Records the calls collect_replays makes to pipelines.raw.replay_collection_run."""

    def __init__(self):
        self.calls = []

    def start(self, conn, format_id):
        self.calls.append(("start", format_id))
        return 3

    def record_replay(self, conn, run_id, outcome):
        self.calls.append(("record_replay", run_id, outcome))

    def finish(self, conn, run_id, status, error=None):
        self.calls.append(("finish", run_id, status, error, conn.rollbacks))


def found(number: int, uploaded_at: datetime) -> SearchResult:
    return SearchResult(f"gen9monotype-{number}", uploaded_at)


# Newest first, as search returns them.
FOUND = [
    found(3, datetime(2026, 3, 5, 23, 0, tzinfo=UTC)),
    SearchResult("rom-gen9monotype-9", datetime(2026, 3, 4, tzinfo=UTC), "rom"),
    found(2, datetime(2026, 3, 3, tzinfo=UTC)),
    found(1, datetime(2026, 3, 1, tzinfo=UTC)),
]


def fake_collect_replays(monkeypatch, stored=(), newest=None, fetch=None, search=None):
    """Fakes collect_replays's database, search, and downloads; returns the connection, run log, and calls made."""
    conn = FakeConnection()
    run = FakeReplayCollectionRun()
    calls = []

    def default_search(format_id, start, end):
        calls.append(("search", format_id, start, end))
        return iter(FOUND)

    def fetch_replay(replay_id):
        calls.append(("fetch", replay_id))
        if fetch:
            fetch(replay_id)
        return replay_id

    monkeypatch.setattr(cli.db, "connect", lambda: conn)
    monkeypatch.setattr(cli, "replay_collection_run", run)
    monkeypatch.setattr(cli.replay, "newest_upload", lambda conn, format_id: newest)
    monkeypatch.setattr(cli.replay, "stored_ids", lambda conn, ids: {i for i in ids if i in stored})
    monkeypatch.setattr(cli.replay, "insert", lambda conn, replay, retrieved_at: calls.append(("insert", replay)))
    monkeypatch.setattr(cli.replays, "search", search or default_search)
    monkeypatch.setattr(cli.replays, "fetch_replay", fetch_replay)
    return conn, run, calls


def test_collect_replays_downloads_a_window_oldest_first(monkeypatch, capsys):
    conn, run, calls = fake_collect_replays(monkeypatch, stored={"gen9monotype-2"})

    cli.collect_replays(date(2026, 3, 1), date(2026, 3, 5))

    assert calls == [
        ("search", "gen9monotype", datetime(2026, 3, 1, tzinfo=UTC), datetime(2026, 3, 6, tzinfo=UTC)),
        ("fetch", "gen9monotype-1"),
        ("insert", "gen9monotype-1"),
        ("fetch", "gen9monotype-3"),
        ("insert", "gen9monotype-3"),
    ]
    assert run.calls == [
        ("start", "gen9monotype"),
        ("record_replay", 3, "loaded"),
        ("record_replay", 3, "loaded"),
        ("finish", 3, "succeeded", None, 0),
    ]
    assert conn.commits == 4
    output = capsys.readouterr().out
    assert output.startswith(
        "Collecting gen9monotype replays uploaded from 2026-03-01 00:00:00 to 2026-03-06 00:00:00 UTC\n"
        "4 found, 1 from other servers skipped, 1 already stored, 2 to download\n"
    )
    assert output.endswith("2 loaded, 0 failed\n")


def test_collect_replays_without_a_window_resumes_from_the_newest_stored(monkeypatch, capsys):
    newest = datetime(2026, 3, 1, tzinfo=UTC)
    _, _, calls = fake_collect_replays(monkeypatch, stored={"gen9monotype-1"}, newest=newest)

    cli.collect_replays(None, None)

    assert calls[0] == ("search", "gen9monotype", newest, None)
    assert "to now UTC" in capsys.readouterr().out


def test_collect_replays_needs_a_window_for_the_first_load(monkeypatch):
    _, run, calls = fake_collect_replays(monkeypatch)

    with pytest.raises(RuntimeError, match="pass --start and --end"):
        cli.collect_replays(None, None)

    assert calls == []
    assert run.calls == []


def test_collect_replays_continues_past_failed_downloads(monkeypatch, capsys):
    def fetch(replay_id):
        if replay_id == "gen9monotype-2":
            raise ReplayFormatError("gen9monotype-2 is not public")

    conn, run, calls = fake_collect_replays(monkeypatch, fetch=fetch)

    with pytest.raises(SystemExit) as exit_info:
        cli.collect_replays(date(2026, 3, 1), date(2026, 3, 5))

    assert exit_info.value.code == 1
    assert [call for call in calls if call[0] == "insert"] == [
        ("insert", "gen9monotype-1"),
        ("insert", "gen9monotype-3"),
    ]
    assert run.calls[1:] == [
        ("record_replay", 3, "loaded"),
        ("record_replay", 3, "failed"),
        ("record_replay", 3, "loaded"),
        ("finish", 3, "partial", None, 0),
    ]
    assert capsys.readouterr().err == (
        "\n1 replays failed; collect their window again to retry them:\n"
        "  gen9monotype-2: gen9monotype-2 is not public\n"
    )


def test_collect_replays_records_a_failed_search(monkeypatch):
    def search(format_id, start, end):
        raise urllib.error.HTTPError("https://replay.pokemonshowdown.com", 503, "Unavailable", Message(), None)

    conn, run, _ = fake_collect_replays(monkeypatch, search=search)

    with pytest.raises(urllib.error.HTTPError):
        cli.collect_replays(date(2026, 3, 1), date(2026, 3, 5))

    assert run.calls[1:] == [("finish", 3, "failed", "HTTPError: HTTP Error 503: Unavailable", 1)]


@pytest.mark.parametrize(
    ("arguments", "window"),
    [
        ([], (None, None)),
        (["--start", "2026-03-01", "--end", "2026-03-05"], (date(2026, 3, 1), date(2026, 3, 5))),
        (["--start", "2026-03-01", "--end", "2026-03-01"], (date(2026, 3, 1), date(2026, 3, 1))),
    ],
)
def test_collect_replays_command(monkeypatch, arguments, window):
    calls = []
    monkeypatch.setattr(cli, "collect_replays", lambda start, end: calls.append((start, end)))
    monkeypatch.setattr("sys.argv", ["pipelines", "collect-replays", *arguments])

    cli.main()

    assert calls == [window]


@pytest.mark.parametrize(
    "arguments",
    [
        ["--start", "2026-03-01"],
        ["--end", "2026-03-05"],
        ["--start", "2026-03-05", "--end", "2026-03-01"],
        ["--start", "March 1", "--end", "2026-03-05"],
    ],
)
def test_collect_replays_command_rejects_bad_windows(monkeypatch, arguments):
    monkeypatch.setattr("sys.argv", ["pipelines", "collect-replays", *arguments])

    with pytest.raises(SystemExit) as exit_info:
        cli.main()

    assert exit_info.value.code == 2


def fake_parse_replays(monkeypatch, logs: dict[str, str]):
    """Fakes parse_replays's database and parser; returns the connection and the battles inserted."""
    conn = FakeConnection()
    inserted = []

    def parse(log, replay_id):
        if log == "bad":
            raise ReplayFormatError(f"{replay_id} has an unknown line type '-newline'")
        return replay_id

    monkeypatch.setattr(cli.db, "connect", lambda: conn)
    monkeypatch.setattr(cli.battle, "unparsed_ids", lambda conn: list(logs))
    monkeypatch.setattr(cli.battle, "all_ids", lambda conn: ["gen9monotype-0", *logs])
    monkeypatch.setattr(cli.battle, "delete", lambda conn, replay_id: inserted.append(("delete", replay_id)))
    monkeypatch.setattr(cli.battle, "log", lambda conn, replay_id: logs[replay_id])
    monkeypatch.setattr(cli.battle, "insert", lambda conn, battle, parsed_at: inserted.append(battle))
    monkeypatch.setattr(cli.battle_log, "parse", parse)
    return conn, inserted


def test_parse_replays_commits_each_battle(monkeypatch, capsys):
    conn, inserted = fake_parse_replays(monkeypatch, {"gen9monotype-1": "ok", "gen9monotype-2": "ok"})

    cli.parse_replays()

    assert inserted == ["gen9monotype-1", "gen9monotype-2"]
    assert conn.commits == 2
    assert capsys.readouterr().out == "2 replays to parse\n2 parsed, 0 failed\n"


def test_parse_replays_continues_past_replays_it_rejects(monkeypatch, capsys):
    conn, inserted = fake_parse_replays(monkeypatch, {"gen9monotype-1": "bad", "gen9monotype-2": "ok"})

    with pytest.raises(SystemExit) as exit_info:
        cli.parse_replays()

    assert exit_info.value.code == 1
    assert inserted == ["gen9monotype-2"]
    assert capsys.readouterr().err == (
        "\n1 replays couldn't be parsed:\n  gen9monotype-1: gen9monotype-1 has an unknown line type '-newline'\n"
    )


def test_parse_replays_reparse_replaces_every_battle_it_can_parse(monkeypatch, capsys):
    logs = {"gen9monotype-0": "ok", "gen9monotype-1": "bad", "gen9monotype-2": "ok"}
    conn, inserted = fake_parse_replays(monkeypatch, logs)
    monkeypatch.setattr(cli.battle, "all_ids", lambda conn: list(logs))

    with pytest.raises(SystemExit):
        cli.parse_replays(reparse=True)

    # The rejected replay keeps its earlier parse: nothing is deleted for it.
    assert inserted == [("delete", "gen9monotype-0"), "gen9monotype-0", ("delete", "gen9monotype-2"), "gen9monotype-2"]
    assert conn.commits == 2
    assert capsys.readouterr().out.startswith("3 replays to re-parse\n")


@pytest.mark.parametrize(("arguments", "reparse"), [([], False), (["--reparse"], True)])
def test_parse_replays_command(monkeypatch, arguments, reparse):
    calls = []
    monkeypatch.setattr(cli, "parse_replays", calls.append)
    monkeypatch.setattr("sys.argv", ["pipelines", "parse-replays", *arguments])

    cli.main()

    assert calls == [reparse]


def fake_update_replays(monkeypatch, loaded=("gen9monotype-1",), failed=(), rejected=(), dbt_statuses=(0, 0)):
    """Fakes update_replays's collection, parse, and dbt calls; returns the calls made, in order."""
    calls = []
    statuses = list(dbt_statuses)

    def collect(start, end):
        calls.append(("collect", start, end))
        return list(loaded), list(failed)

    def parse(replay_ids, reparse=False):
        calls.append(("parse", replay_ids))
        return list(rejected)

    def run(command, check):
        calls.append(("dbt", command[command.index("--select") + 1 : command.index("--project-dir")]))
        return subprocess.CompletedProcess(command, statuses.pop(0))

    monkeypatch.setattr(cli.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(cli, "collect", collect)
    monkeypatch.setattr(cli, "parse", parse)
    monkeypatch.setattr(cli.subprocess, "run", run)
    return calls


STAGING = ["path:models/staging/stg_battle*"]
API = ["path:models/api/battle", "path:models/api/replay"]


def test_update_replays_collects_parses_and_builds_only_the_replay_models(monkeypatch):
    calls = fake_update_replays(monkeypatch, loaded=["gen9monotype-1", "gen9monotype-2"])

    cli.update_replays()

    assert calls == [
        ("collect", None, None),
        ("parse", ["gen9monotype-1", "gen9monotype-2"]),
        ("dbt", STAGING),
        ("dbt", API),
    ]


def test_update_replays_lists_rejected_replays_without_failing(monkeypatch, capsys):
    rejected = [("gen9monotype-2", ReplayFormatError("gen9monotype-2 has an unknown line type 'error'"))]
    calls = fake_update_replays(monkeypatch, rejected=rejected)

    cli.update_replays()

    assert calls[-1] == ("dbt", API)
    assert capsys.readouterr().out == (
        "\n1 replays couldn't be parsed and were left out:\n"
        "  gen9monotype-2: gen9monotype-2 has an unknown line type 'error'\n"
    )


def test_update_replays_builds_then_fails_after_failed_downloads(monkeypatch, capsys):
    failed = [("gen9monotype-3", ReplayFormatError("gen9monotype-3 is not public"))]
    calls = fake_update_replays(monkeypatch, failed=failed)

    with pytest.raises(SystemExit) as exit_info:
        cli.update_replays()

    assert exit_info.value.code == 1
    assert calls[-1] == ("dbt", API)
    assert capsys.readouterr().err == (
        "\n1 replays failed to download; collect their window again to retry them:\n"
        "  gen9monotype-3: gen9monotype-3 is not public\n"
    )


def test_update_replays_skips_api_when_staging_fails(monkeypatch):
    calls = fake_update_replays(monkeypatch, dbt_statuses=(1,))

    with pytest.raises(SystemExit) as exit_info:
        cli.update_replays()

    assert exit_info.value.code == 1
    assert calls[-1] == ("dbt", STAGING)


def test_update_replays_requires_dbt_before_collecting(monkeypatch):
    calls = fake_update_replays(monkeypatch)
    monkeypatch.setattr(cli.shutil, "which", lambda name: None)

    with pytest.raises(RuntimeError, match="dbt is not installed"):
        cli.update_replays()

    assert calls == []


def test_update_replays_command(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "update_replays", lambda: calls.append("update"))
    monkeypatch.setattr("sys.argv", ["pipelines", "update-replays"])

    cli.main()

    assert calls == ["update"]
