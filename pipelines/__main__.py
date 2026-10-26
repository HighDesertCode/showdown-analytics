"""Entry point: `uv run --env-file .env pipelines <command>`."""

import argparse

from pipelines import db, showdown
from pipelines.reference.load import load_all


def check_connection() -> None:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT current_user, current_database(), ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()"
        ).fetchone()
    if row is None:
        raise RuntimeError("Could not read connection details")
    user, database, ssl = row
    print(f"Connected to {database} as {user} (SSL: {ssl})")


def load_reference() -> None:
    # Fetch everything before connecting, so a network failure never leaves a partial load.
    sources = {name: showdown.load(name) for name in showdown.SOURCES}
    # The connection block commits if every loader succeeds and rolls back if any one fails.
    with db.connect() as conn:
        counts = load_all(conn, sources)
    for table, count in counts.items():
        print(f"{table:<16} {count:>5} inserted")


COMMANDS = {
    "check-connection": check_connection,
    "load-reference": load_reference,
}


def main() -> None:
    parser = argparse.ArgumentParser(prog="pipelines")
    parser.add_argument("command", choices=COMMANDS)
    args = parser.parse_args()
    COMMANDS[args.command]()


if __name__ == "__main__":
    main()
