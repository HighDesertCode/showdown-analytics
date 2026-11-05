import os
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from api import db
from api.db import create_pool
from api.main import create_app


def test_health_reports_ok_when_the_database_answers(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def unreachable_pool() -> ConnectionPool:
    # Nothing listens on port 1, so every connection attempt fails.
    return ConnectionPool("postgresql://localhost:1/none", min_size=1, max_size=1, open=False, timeout=1)


def test_health_reports_unavailable_when_the_database_is_unreachable(monkeypatch):
    monkeypatch.setattr("api.main.HEALTH_TIMEOUT_SECONDS", 1)
    with TestClient(create_app(unreachable_pool())) as client:
        response = client.get("/health")

    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"
    assert response.json() == {"detail": "Database unavailable; try again shortly."}


def test_a_query_past_the_statement_timeout_is_a_503_with_a_retry_hint():
    app = create_app(unreachable_pool())

    @app.get("/timeout")
    def timeout() -> None:
        raise psycopg.errors.QueryCanceled("canceling statement due to statement timeout")

    with TestClient(app) as client:
        response = client.get("/timeout")

    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"
    assert response.json() == {
        "detail": "The query took too long; try again shortly, with a smaller limit or a narrower filter."
    }


@pytest.mark.parametrize(
    ("path", "params", "detail"),
    [
        ("/v1/smogon/pokemon/!!!", {}, "'!!!' isn't a species"),
        ("/v1/smogon/usage", {"team_type": "!"}, "'!' isn't a type"),
        ("/v1/replays/leads", {"team_type": "!"}, "'!' isn't a type"),
        ("/v1/battles", {"player": "!!"}, "'!!' isn't a player name"),
        ("/v1/reference/types/!!", {}, "'!!' isn't a type"),
    ],
)
def test_a_name_with_no_letters_or_digits_is_rejected_before_any_lookup(client, path, params, detail):
    # Every router validates through params.showdown_id, and before touching the database: the tables are empty here.
    response = client.get(path, params=params)

    assert response.status_code == 422
    assert response.json() == {"detail": detail}


@pytest.mark.parametrize("path", ["/v1/smogon/usage", "/v1/replays/sample", "/v1/battles"])
@pytest.mark.parametrize("month", ["0000-01", "9999-12", "1999-12"])
def test_a_month_outside_2000_to_2099_is_rejected_rather_than_failing(client, path, month):
    # The date helpers can't build year 0, or the end of 9999-12, so these must never reach them.
    response = client.get(path, params={"month": month})

    assert response.status_code == 422


def test_openapi_names_each_operation_after_its_group_and_endpoint():
    spec = create_app().openapi()

    ids = [operation["operationId"] for operations in spec["paths"].values() for operation in operations.values()]
    assert len(ids) == len(set(ids))
    assert spec["paths"]["/v1/smogon/pokemon/{species}/{section}"]["get"]["operationId"] == "smogon_pokemon_section"
    assert spec["paths"]["/v1/replays/type-matchups"]["get"]["operationId"] == "replays_type_matchups"
    assert spec["paths"]["/v1/battles/{replay_id}/events"]["get"]["operationId"] == "battles_events"
    assert spec["paths"]["/health"]["get"]["operationId"] == "health"


def test_openapi_pins_each_endpoints_scope_type():
    spec = create_app().openapi()
    schemas = spec["components"]["schemas"]

    def scope_of(path):
        response = spec["paths"][path]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        envelope = schemas[response["$ref"].rsplit("/", 1)[1]]
        return envelope["properties"]["scope"]["$ref"].rsplit("/", 1)[1]

    assert scope_of("/v1/smogon/usage") == "SmogonScope"
    assert scope_of("/v1/replays/leads") == "ReplayScope"
    assert scope_of("/v1/battles") == "BattleScope"
    assert scope_of("/v1/reference/{kind}") == "ReferenceScope"


def test_openapi_describes_every_operation_parameter_and_field():
    # Agents read these descriptions, so none may be left out.
    spec = create_app().openapi()

    undescribed = []
    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            if not operation.get("description"):
                undescribed.append(f"{method.upper()} {path}")
            undescribed += [f"{path}?{p['name']}" for p in operation.get("parameters", []) if not p.get("description")]
    for name, schema in spec["components"]["schemas"].items():
        if name in ("HTTPValidationError", "ValidationError"):
            continue
        undescribed += [
            f"{name}.{f}" for f, prop in schema.get("properties", {}).items() if not prop.get("description")
        ]

    assert undescribed == []


@pytest.fixture
def api_settings(monkeypatch):
    for name, value in {
        "PGHOST": "db.example.com",
        "PGDATABASE": "showdown-database",
        "PGUSER": "showdown-api",
        "PGSSLMODE": "verify-full",
    }.items():
        monkeypatch.setenv(name, value)
    # Deleting them through monkeypatch also restores them after the test, since create_pool can set PGSSLROOTCERT.
    monkeypatch.delenv("DATABASE_CA_CERT", raising=False)
    monkeypatch.delenv("PGSSLROOTCERT", raising=False)


def test_create_pool_accepts_the_api_role_with_verified_tls(api_settings):
    pool = create_pool()

    assert pool.max_size == 4


def test_create_pool_runs_in_autocommit_mode_with_dict_rows(api_settings):
    assert create_pool().kwargs == {"autocommit": True, "row_factory": dict_row}


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


PEM = "-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n"


@pytest.fixture
def temp_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(db.tempfile, "gettempdir", lambda: str(tmp_path))
    return tmp_path


def test_create_pool_writes_the_ca_certificate_from_the_environment_for_libpq(api_settings, temp_dir, monkeypatch):
    # App Platform supplies the attached database's certificate as text; libpq reads it only from a file.
    monkeypatch.setenv("DATABASE_CA_CERT", PEM)

    create_pool()

    path = Path(os.environ["PGSSLROOTCERT"])
    assert path.parent == temp_dir
    assert path.read_text() == PEM
    assert path.stat().st_mode & 0o777 == 0o600


def test_create_pool_leaves_the_certificate_file_alone_without_the_setting(api_settings, temp_dir, monkeypatch):
    monkeypatch.setenv("PGSSLROOTCERT", "/etc/ssl/ca.crt")

    create_pool()

    assert os.environ["PGSSLROOTCERT"] == "/etc/ssl/ca.crt"
    assert list(temp_dir.iterdir()) == []


def test_create_pool_refuses_both_certificate_settings(api_settings, temp_dir, monkeypatch):
    monkeypatch.setenv("DATABASE_CA_CERT", PEM)
    monkeypatch.setenv("PGSSLROOTCERT", "/etc/ssl/ca.crt")

    with pytest.raises(RuntimeError, match="not both"):
        create_pool()


def test_create_pool_refuses_a_certificate_setting_that_is_not_a_certificate(api_settings, temp_dir, monkeypatch):
    # An unfilled App Platform placeholder, for example.
    monkeypatch.setenv("DATABASE_CA_CERT", "${db.CA_CERT}")

    with pytest.raises(RuntimeError, match="PEM certificate"):
        create_pool()

    assert "PGSSLROOTCERT" not in os.environ
