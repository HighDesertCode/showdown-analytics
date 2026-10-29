import pytest

from pipelines import db

SETTINGS = {
    "PGHOST": "db.example.com",
    "PGDATABASE": "showdown-database",
    "PGUSER": "showdown-analyst",
    "PGSSLMODE": "verify-full",
}


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


@pytest.mark.parametrize("sslmode", [None, "disable", "prefer", "require", "verify-ca"])
def test_connect_requires_verify_full_for_remote_host(settings, monkeypatch, sslmode):
    if sslmode is None:
        monkeypatch.delenv("PGSSLMODE")
    else:
        monkeypatch.setenv("PGSSLMODE", sslmode)

    with pytest.raises(RuntimeError, match="verify-full"):
        db.connect()


@pytest.mark.parametrize("host", db.LOCAL_HOSTS)
def test_connect_allows_local_host_without_verify_full(settings, monkeypatch, host):
    monkeypatch.setenv("PGHOST", host)
    monkeypatch.setenv("PGSSLMODE", "disable")
    monkeypatch.setattr(db.psycopg, "connect", lambda *args, **kwargs: "conn")

    assert db.connect() == "conn"
