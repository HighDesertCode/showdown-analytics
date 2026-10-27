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
