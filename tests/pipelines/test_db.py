import os
from pathlib import Path

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


PEM = "-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n"


@pytest.fixture
def temp_dir(monkeypatch, tmp_path):
    """Writes the certificate under tmp_path, and restores PGSSLROOTCERT after the test."""
    monkeypatch.setattr(db.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.delenv("PGSSLROOTCERT", raising=False)
    return tmp_path


def test_use_ca_cert_writes_the_certificate_and_points_libpq_at_it(temp_dir, monkeypatch):
    monkeypatch.setenv("DATABASE_CA_CERT", PEM)

    db.use_ca_cert_from_environment()

    path = Path(os.environ["PGSSLROOTCERT"])
    assert path.parent == temp_dir
    assert path.name.startswith("database-ca-")
    assert path.read_text() == PEM
    assert path.stat().st_mode & 0o777 == 0o600


def test_use_ca_cert_gives_each_command_its_own_file(temp_dir, monkeypatch):
    monkeypatch.setenv("DATABASE_CA_CERT", PEM)
    paths = []
    for _ in range(2):
        db.use_ca_cert_from_environment()
        paths.append(os.environ.pop("PGSSLROOTCERT"))

    assert paths[0] != paths[1]
    assert all(Path(path).read_text() == PEM for path in paths)


def test_use_ca_cert_does_nothing_without_the_setting(temp_dir, monkeypatch):
    monkeypatch.delenv("DATABASE_CA_CERT", raising=False)

    db.use_ca_cert_from_environment()

    assert "PGSSLROOTCERT" not in os.environ
    assert list(temp_dir.iterdir()) == []


def test_use_ca_cert_refuses_both_settings(temp_dir, monkeypatch):
    monkeypatch.setenv("DATABASE_CA_CERT", PEM)
    monkeypatch.setenv("PGSSLROOTCERT", "/etc/ssl/ca.crt")

    with pytest.raises(RuntimeError, match="not both"):
        db.use_ca_cert_from_environment()


def test_use_ca_cert_refuses_text_that_is_not_a_certificate(temp_dir, monkeypatch):
    monkeypatch.setenv("DATABASE_CA_CERT", "${db.CA_CERT}")

    with pytest.raises(RuntimeError, match="PEM certificate"):
        db.use_ca_cert_from_environment()

    assert "PGSSLROOTCERT" not in os.environ
