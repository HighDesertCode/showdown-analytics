from datetime import date

import pytest

from pipelines import __main__ as cli


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, query):
        return self

    def fetchone(self):
        return ("showdown-analyst", "showdown-database", True)


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
