import pytest

from pipelines import db

SETTINGS = {"PGHOST": "db.example.com", "PGDATABASE": "showdown-database", "PGUSER": "showdown-analyst"}


@pytest.fixture
def settings(monkeypatch):
    for name, value in SETTINGS.items():
        monkeypatch.setenv(name, value)


def test_connect_uses_environment_settings(settings, monkeypatch):
    calls = []
    monkeypatch.setattr(db.psycopg, "connect", lambda *args, **kwargs: calls.append((args, kwargs)) or "conn")

    assert db.connect() == "conn"
    assert calls == [((), {})]


@pytest.mark.parametrize("name", db.REQUIRED_SETTINGS)
def test_connect_requires_setting(settings, monkeypatch, name):
    monkeypatch.delenv(name)

    with pytest.raises(RuntimeError, match=name):
        db.connect()


def test_connect_refuses_defaultdb(settings, monkeypatch):
    monkeypatch.setenv("PGDATABASE", "defaultdb")

    with pytest.raises(RuntimeError, match="defaultdb"):
        db.connect()
