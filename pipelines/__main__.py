"""Entry point: `uv run --env-file .env pipelines <command>`."""

import argparse
import sys
from datetime import date

from pipelines import db, download, showdown, smogon
from pipelines.raw.load import load_file
from pipelines.reference.common import existing_ids
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


def load_smogon(month: date, families: list[str]) -> None:
    with db.connect() as conn:
        type_ids = existing_ids(conn, "type")
        if not type_ids:
            # Without types, only overall reports would be listed and per-type reports silently skipped.
            raise RuntimeError("reference.type is empty; run `pipelines load-reference` first")
        team_types = sorted(type_ids, key=type_ids.__getitem__)
        files = [file for family in families for file in smogon.report_files(family, month, team_types)]
        width = max(len(family) for family in families)
        failed: list[tuple[smogon.ReportFile, Exception]] = []
        for file in files:
            scope = f"mono{file.team_type}" if file.team_type else "overall"
            try:
                counts = load_file(conn, file, type_ids.get(file.team_type) if file.team_type else None)
            except download.NETWORK_ERRORS as error:
                # The download comes before any insert, so there is nothing to roll back; a rerun loads the file.
                failed.append((file, error))
                print(f"{file.family:<{width}} {scope:<14} {file.baseline}  failed ({error})")
                continue
            # Commit each file on its own: a later failure keeps earlier files, and a rerun skips them.
            conn.commit()
            if counts is None:
                result = "skipped (already loaded)"
            else:
                result = "loaded " + "  ".join(f"{count:>6,} {table}" for table, count in counts.items())
            print(f"{file.family:<{width}} {scope:<14} {file.baseline}  {result}")
    if failed:
        print(f"\n{len(failed)} of {len(files)} files failed to download; rerun to load them:", file=sys.stderr)
        for file, error in failed:
            print(f"  {file.url}: {error}", file=sys.stderr)
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(prog="pipelines")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check-connection", help="check the database connection")
    commands.add_parser("load-reference", help="load Showdown reference data")
    load_smogon_parser = commands.add_parser("load-smogon", help="load one month of Smogon reports")
    load_smogon_parser.add_argument("month", type=smogon.parse_month, help="the report month, e.g. 2026-09")
    load_smogon_parser.add_argument(
        "--family",
        action="append",
        choices=list(smogon.FAMILIES),
        help="load only this report family; repeat for several (default: every family)",
    )
    args = parser.parse_args()

    if args.command == "check-connection":
        check_connection()
    elif args.command == "load-reference":
        load_reference()
    elif args.command == "load-smogon":
        load_smogon(args.month, args.family or list(smogon.FAMILIES))


if __name__ == "__main__":
    main()
