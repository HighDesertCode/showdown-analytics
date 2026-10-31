"""PostgreSQL connections for pipelines.

Settings come from libpq's standard PG* environment variables (PGHOST, PGDATABASE, PGUSER, ...),
loaded from .env by `uv run --env-file .env`. Connections to any database that isn't local require
PGSSLMODE=verify-full, so the server's certificate and hostname are always checked; libpq's default doesn't.
"""

import os
import tempfile
from pathlib import Path

import psycopg

REQUIRED_SETTINGS = ("PGHOST", "PGDATABASE", "PGUSER")
LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")
# Holds the CA certificate's text where it can't be a file, as in App Platform's environment variables.
CA_CERT_SETTING = "DATABASE_CA_CERT"


def connect() -> psycopg.Connection:
    missing = [name for name in REQUIRED_SETTINGS if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"Missing database settings: {', '.join(missing)}")
    if os.environ["PGDATABASE"] == "defaultdb":
        raise RuntimeError("Refusing to connect to defaultdb; project data belongs in showdown-database.")
    if os.environ["PGHOST"] not in LOCAL_HOSTS and os.environ.get("PGSSLMODE") != "verify-full":
        raise RuntimeError("Refusing to connect without PGSSLMODE=verify-full to a database that isn't local.")
    return psycopg.connect()


def use_ca_cert_from_environment() -> None:
    """Writes the certificate in DATABASE_CA_CERT to a file and points PGSSLROOTCERT at it.

    libpq reads the CA certificate only from a file. Setting PGSSLROOTCERT in this process's environment also
    covers dbt, which runs as a child process. Does nothing when DATABASE_CA_CERT isn't set.
    """
    pem = os.environ.get(CA_CERT_SETTING)
    if not pem:
        return
    if os.environ.get("PGSSLROOTCERT"):
        raise RuntimeError(f"Set {CA_CERT_SETTING} or PGSSLROOTCERT, not both")
    if not pem.lstrip().startswith("-----BEGIN CERTIFICATE-----"):
        raise RuntimeError(f"{CA_CERT_SETTING} doesn't hold a PEM certificate")
    path = Path(tempfile.gettempdir()) / "database-ca.crt"
    path.write_text(pem)
    os.environ["PGSSLROOTCERT"] = str(path)
