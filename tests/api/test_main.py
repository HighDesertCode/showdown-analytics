import pytest
from fastapi.testclient import TestClient
from psycopg_pool import ConnectionPool

from api.db import create_pool
from api.main import create_app


def test_health_reports_ok_when_the_database_answers(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_reports_unavailable_when_the_database_is_unreachable():
    # Nothing listens on port 1, so every connection attempt fails.
    pool = ConnectionPool("postgresql://localhost:1/none", min_size=1, max_size=1, open=False, timeout=1)
    with TestClient(create_app(pool)) as client:
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}


@pytest.fixture
def api_settings(monkeypatch):
    for name, value in {
        "PGHOST": "db.example.com",
        "PGDATABASE": "showdown-database",
        "PGUSER": "showdown-api",
        "PGSSLMODE": "verify-full",
    }.items():
        monkeypatch.setenv(name, value)


def test_create_pool_accepts_the_api_role_with_verified_tls(api_settings):
    pool = create_pool()

    assert pool.max_size == 4


@pytest.mark.parametrize("user", ["showdown-analyst", "showdown-transform", "doadmin"])
def test_create_pool_refuses_other_roles(api_settings, monkeypatch, user):
    monkeypatch.setenv("PGUSER", user)

    with pytest.raises(RuntimeError, match="connects only as showdown-api"):
        create_pool()


def test_create_pool_refuses_unverified_tls_to_a_remote_database(api_settings, monkeypatch):
    monkeypatch.setenv("PGSSLMODE", "require")

    with pytest.raises(RuntimeError, match="verify-full"):
        create_pool()


def test_create_pool_requires_settings(api_settings, monkeypatch):
    monkeypatch.delenv("PGHOST")

    with pytest.raises(RuntimeError, match="PGHOST"):
        create_pool()
