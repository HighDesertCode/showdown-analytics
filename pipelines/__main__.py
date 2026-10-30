"""Entry point: `uv run --env-file .env pipelines <command>`."""

import argparse
import shutil
import subprocess
import sys
from datetime import UTC, date, datetime, timedelta

from psycopg import Connection

from pipelines import db, download, showdown, smogon
from pipelines.raw import ingestion_run, source_file
from pipelines.raw.load import load_file
from pipelines.reference.common import existing_ids
from pipelines.reference.load import load_all

# Relative to the working directory: the repository root locally, and /app in the image.
TRANSFORM_DIR = "transform"


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


def list_report_files(
    conn: Connection, month: date, families: list[str]
) -> tuple[list[smogon.ReportFile], dict[str, int]]:
    """Lists the month's files for each family, with the type_id of each team type."""
    type_ids = existing_ids(conn, "type")
    if not type_ids:
        # Without types, only overall reports would be listed and per-type reports silently skipped.
        raise RuntimeError("reference.type is empty; run `pipelines load-reference` first")
    team_types = sorted(type_ids, key=type_ids.__getitem__)
    return [file for family in families for file in smogon.report_files(family, month, team_types)], type_ids


def load_smogon(month: date, families: list[str]) -> None:
    with db.connect() as conn:
        files, type_ids = list_report_files(conn, month, families)
        width = max(len(family) for family in families)
        failed: list[tuple[smogon.ReportFile, Exception]] = []
        run_id = ingestion_run.start(conn, month, families)
        conn.commit()
        try:
            for file in files:
                scope = f"mono{file.team_type}" if file.team_type else "overall"
                try:
                    counts = load_file(conn, file, type_ids.get(file.team_type) if file.team_type else None)
                except download.NETWORK_ERRORS as error:
                    # The download comes before any insert, so there is nothing to roll back; a rerun loads the file.
                    failed.append((file, error))
                    ingestion_run.record_file(conn, run_id, "failed")
                    conn.commit()
                    print(f"{file.family:<{width}} {scope:<14} {file.baseline}  failed ({error})")
                    continue
                # Commit each file on its own: a later failure keeps earlier files, and a rerun skips them. The run's
                # count commits with the file's rows, so its progress is exact even if the run is killed.
                ingestion_run.record_file(conn, run_id, "skipped" if counts is None else "loaded")
                conn.commit()
                if counts is None:
                    result = "skipped (already loaded)"
                else:
                    result = "loaded " + "  ".join(f"{count:>6,} {table}" for table, count in counts.items())
                print(f"{file.family:<{width}} {scope:<14} {file.baseline}  {result}")
        except Exception as error:
            # Discard the failed file's partial work, then record why the run stopped.
            conn.rollback()
            ingestion_run.finish(conn, run_id, "failed", f"{type(error).__name__}: {error}")
            conn.commit()
            raise
        ingestion_run.finish(conn, run_id, "partial" if failed else "succeeded")
        conn.commit()
    if failed:
        print(f"\n{len(failed)} of {len(files)} files failed to download; rerun to load them:", file=sys.stderr)
        for file, error in failed:
            print(f"  {file.url}: {error}", file=sys.stderr)
        raise SystemExit(1)


def previous_month(today: date) -> date:
    return (today.replace(day=1) - timedelta(days=1)).replace(day=1)


def update_smogon(today: date) -> None:
    """Loads last month's Smogon reports once Smogon publishes them, then builds staging and api.

    Run daily by the scheduled job. It downloads nothing once the month is loaded, and makes one HEAD request
    a day until Smogon publishes it.
    """
    month = previous_month(today)
    families = list(smogon.FAMILIES)
    # Checked first, so a missing dbt fails the job before anything is loaded.
    if shutil.which("dbt") is None:
        raise RuntimeError("dbt is not installed; run with `uv run --group dbt`")
    with db.connect() as conn:
        files, _ = list_report_files(conn, month, families)
        missing = source_file.missing_urls(conn, [file.url for file in files])
    if not missing:
        print(f"{month:%Y-%m} is already loaded")
        return
    if not download.exists(smogon.url("usage", month, smogon.BASELINES[0])):
        print(f"{month:%Y-%m} isn't published yet")
        return
    print(f"{month:%Y-%m}: loading {len(missing)} of {len(files)} files")
    load_smogon(month, families)
    # Staging first, so a failed staging test (such as a month missing files) leaves every api table untouched.
    for selector in ("staging", "api"):
        run_dbt("build", "--select", selector)


def run_dbt(*arguments: str) -> None:
    """Runs dbt on the transform project, exiting with dbt's status if it fails."""
    # Flush first, so this command's output stays ahead of dbt's in the job's logs.
    sys.stdout.flush()
    command = ["dbt", *arguments, "--project-dir", TRANSFORM_DIR, "--profiles-dir", TRANSFORM_DIR]
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        print(f"`{' '.join(command)}` failed with status {result.returncode}", file=sys.stderr)
        raise SystemExit(result.returncode)


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
    commands.add_parser(
        "update-smogon", help="load last month's Smogon reports if published and not yet loaded, then run dbt"
    )
    args = parser.parse_args()

    if args.command == "check-connection":
        check_connection()
    elif args.command == "load-reference":
        load_reference()
    elif args.command == "load-smogon":
        load_smogon(args.month, args.family or list(smogon.FAMILIES))
    elif args.command == "update-smogon":
        update_smogon(datetime.now(UTC).date())


if __name__ == "__main__":
    main()
