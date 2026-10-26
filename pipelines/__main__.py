"""Entry point: `uv run --env-file .env python -m pipelines <command>`."""

import argparse

from pipelines import db


def check_connection() -> None:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT current_user, current_database(), ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()"
        ).fetchone()
    if row is None:
        raise RuntimeError("Could not read connection details")
    user, database, ssl = row
    print(f"Connected to {database} as {user} (SSL: {ssl})")


COMMANDS = {
    "check-connection": check_connection,
}


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m pipelines")
    parser.add_argument("command", choices=COMMANDS)
    args = parser.parse_args()
    COMMANDS[args.command]()


if __name__ == "__main__":
    main()
