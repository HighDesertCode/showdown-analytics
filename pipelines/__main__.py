"""Entry point: `uv run --env-file .env pipelines <command>`."""

import argparse
import shutil
import subprocess
import sys
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, date, datetime, time, timedelta
from typing import TextIO

from psycopg import Connection

from pipelines import battle_log, db, download, replays, showdown, smogon
from pipelines.raw import battle, ingestion_run, replay, replay_collection_run, source_file
from pipelines.raw.load import load_file
from pipelines.reference.common import existing_ids
from pipelines.reference.load import load_all

# Relative to the working directory: the repository root locally, and /app in the image.
TRANSFORM_DIR = "transform"
# The replay models and the staging views they read, built daily without touching the monthly Smogon models.
REPLAY_STAGING = ("path:models/staging/stg_battle*",)
REPLAY_API = ("path:models/api/battle", "path:models/api/replay")
# Any fixed number: the Postgres advisory lock every scheduled command holds while dbt builds.
DBT_LOCK = 4271983


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
    with dbt_lock():
        for selector in ("staging", "api"):
            run_dbt("build", "--select", selector)


@contextmanager
def dbt_lock() -> Generator[None]:
    """Holds a database-wide lock while dbt builds, so two jobs never replace the same views and tables at once.

    Postgres releases it when the connection closes, even if the process is killed.
    """
    with db.connect() as conn:
        # Autocommit, so the connection waits idle rather than holding a transaction open through the build.
        conn.autocommit = True
        row = conn.execute("SELECT PG_TRY_ADVISORY_LOCK(%s)", (DBT_LOCK,)).fetchone()
        if not (row and row[0]):
            print("Waiting for another dbt build to finish")
            sys.stdout.flush()
            conn.execute("SELECT PG_ADVISORY_LOCK(%s)", (DBT_LOCK,))
        yield


def run_dbt(*arguments: str) -> None:
    """Runs dbt on the transform project, exiting with dbt's status if it fails."""
    # Flush first, so this command's output stays ahead of dbt's in the job's logs.
    sys.stdout.flush()
    command = ["dbt", *arguments, "--project-dir", TRANSFORM_DIR, "--profiles-dir", TRANSFORM_DIR]
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        print(f"`{' '.join(command)}` failed with status {result.returncode}", file=sys.stderr)
        raise SystemExit(result.returncode)


def collect_replays(start: date | None, end: date | None) -> None:
    loaded, failed = collect(start, end)
    if failed:
        report(failed, "replays failed; collect their window again to retry them")
        raise SystemExit(1)


def collect(start: date | None, end: date | None) -> tuple[list[str], list[tuple[str, Exception]]]:
    """Stores the public replays uploaded from `start` through `end` (UTC days), or, with no window, those uploaded
    since the newest one already stored, and returns the IDs it stored and the replays that failed.

    Every search page is read first, then replays are downloaded oldest first and committed one at a time, so a
    killed run never leaves a gap below the newest stored replay, where the next run resumes.
    """
    format_id = replays.FORMAT_ID
    with db.connect() as conn:
        if start is None or end is None:
            since = replay.newest_upload(conn, format_id)
            if since is None:
                raise RuntimeError("raw.replay is empty; pass --start and --end for the first load")
            until = None
        else:
            since = datetime.combine(start, time(), UTC)
            until = datetime.combine(end + timedelta(days=1), time(), UTC)
        print(
            f"Collecting {format_id} replays uploaded from {since:%Y-%m-%d %H:%M:%S} to "
            f"{'now' if until is None else f'{until:%Y-%m-%d %H:%M:%S}'} UTC"
        )
        loaded: list[str] = []
        failed: list[tuple[str, Exception]] = []
        run_id = replay_collection_run.start(conn, format_id)
        conn.commit()
        try:
            found = list(replays.search(format_id, since, until))
            # Side servers have their own ratings and players (including bots), so only the main server's are kept.
            main_server = [result for result in found if result.server is None]
            stored = replay.stored_ids(conn, [result.replay_id for result in main_server])
            new = [result for result in reversed(main_server) if result.replay_id not in stored]
            print(
                f"{len(found)} found, {len(found) - len(main_server)} from other servers skipped, "
                f"{len(main_server) - len(new)} already stored, {len(new)} to download"
            )
            for result in new:
                try:
                    downloaded = replays.fetch_replay(result.replay_id)
                except (*download.NETWORK_ERRORS, replays.ReplayFormatError) as error:
                    # Nothing was inserted, so there is nothing to roll back; a run over the same window retries it.
                    failed.append((result.replay_id, error))
                    replay_collection_run.record_replay(conn, run_id, "failed")
                    conn.commit()
                    print(f"{result.replay_id}  {result.uploaded_at:%Y-%m-%d %H:%M:%S}  failed ({error})")
                    continue
                # The run's count commits with the replay, so its progress is exact even if the run is killed.
                replay.insert(conn, downloaded, datetime.now(UTC))
                replay_collection_run.record_replay(conn, run_id, "loaded")
                conn.commit()
                loaded.append(result.replay_id)
                print(f"{result.replay_id}  {result.uploaded_at:%Y-%m-%d %H:%M:%S}  loaded")
        except Exception as error:
            conn.rollback()
            replay_collection_run.finish(conn, run_id, "failed", f"{type(error).__name__}: {error}")
            conn.commit()
            raise
        replay_collection_run.finish(conn, run_id, "partial" if failed else "succeeded")
        conn.commit()
    print(f"{len(loaded)} loaded, {len(failed)} failed")
    return loaded, failed


def parse_replays(reparse: bool = False) -> None:
    """Parses every stored replay that has no parsed battle yet, or with `reparse`, every stored replay again.

    A replay the parser rejects is listed at the end, and the command exits with status 1; once the parser handles
    it, a rerun parses it.
    """
    with db.connect() as conn:
        replay_ids = battle.all_ids(conn) if reparse else battle.unparsed_ids(conn)
    failed = parse(replay_ids, reparse)
    if failed:
        report(failed, "replays couldn't be parsed")
        raise SystemExit(1)


def parse(replay_ids: list[str], reparse: bool = False) -> list[tuple[str, Exception]]:
    """Parses the given stored replays, with `reparse` replacing their earlier parses, and returns those rejected.

    Each battle is parsed, and with `reparse` its old parse deleted, then inserted and committed on its own, so a
    battle never mixes two parses. A replay the parser rejects keeps its old parse (or stays unparsed).
    """
    with db.connect() as conn:
        print(f"{len(replay_ids)} replays to {'re-parse' if reparse else 'parse'}")
        failed: list[tuple[str, Exception]] = []
        for replay_id in replay_ids:
            try:
                parsed = battle_log.parse(battle.log(conn, replay_id), replay_id)
            except replays.ReplayFormatError as error:
                failed.append((replay_id, error))
                continue
            if reparse:
                battle.delete(conn, replay_id)
            battle.insert(conn, parsed, datetime.now(UTC))
            conn.commit()
    print(f"{len(replay_ids) - len(failed)} parsed, {len(failed)} failed")
    return failed


def update_replays() -> None:
    """Collects the replays uploaded since the newest stored one, parses every unparsed replay, then builds the
    replay models.

    Run daily by the scheduled job. Parsing every unparsed replay, not just this run's, picks up any an interrupted
    run stored without parsing. A replay the parser rejects doesn't fail the job, since it would be rejected again
    every day; new rejections are listed and earlier ones counted. A failed search, download, or dbt build does fail
    it. dbt builds only the replay models, staging first, so a failed staging test leaves every api table untouched.
    """
    # Checked first, so a missing dbt fails the job before anything is collected.
    if shutil.which("dbt") is None:
        raise RuntimeError("dbt is not installed; run with `uv run --group dbt`")
    loaded, failed = collect(None, None)
    with db.connect() as conn:
        unparsed = battle.unparsed_ids(conn)
    rejected = parse(unparsed)
    stored_now = set(loaded)
    if new_rejections := [failure for failure in rejected if failure[0] in stored_now]:
        report(new_rejections, "new replays couldn't be parsed and were left out", file=sys.stdout)
    if earlier := len(rejected) - len(new_rejections):
        print(f"{earlier} replays stored before this run still couldn't be parsed")
    with dbt_lock():
        for selectors in (REPLAY_STAGING, REPLAY_API):
            run_dbt("build", "--select", *selectors)
    if failed:
        report(failed, "replays failed to download; collect their window again to retry them")
        raise SystemExit(1)


def report(failures: list[tuple[str, Exception]], message: str, file: TextIO | None = None) -> None:
    """Lists replays that failed, to stderr unless `file` is given."""
    # Looked up on each call rather than as the default, which would keep the stderr from import time.
    file = file or sys.stderr
    print(f"\n{len(failures)} {message}:", file=file)
    for replay_id, error in failures:
        print(f"  {replay_id}: {error}", file=file)


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
    collect_parser = commands.add_parser(
        "collect-replays",
        help="store public Monotype replays uploaded in a window, or since the newest stored one",
    )
    collect_parser.add_argument("--start", type=date.fromisoformat, help="first upload day (UTC), e.g. 2026-03-01")
    collect_parser.add_argument("--end", type=date.fromisoformat, help="last upload day (UTC), included")
    commands.add_parser(
        "update-replays", help="collect replays uploaded since the newest stored one, parse them, then run dbt"
    )
    parse_parser = commands.add_parser("parse-replays", help="parse stored replays that haven't been parsed yet")
    parse_parser.add_argument(
        "--reparse", action="store_true", help="parse every stored replay again, replacing its earlier parse"
    )
    args = parser.parse_args()
    if args.command == "collect-replays":
        if (args.start is None) != (args.end is None):
            collect_parser.error("--start and --end go together")
        if args.start is not None and args.start > args.end:
            collect_parser.error("--start is after --end")
    db.use_ca_cert_from_environment()

    if args.command == "check-connection":
        check_connection()
    elif args.command == "load-reference":
        load_reference()
    elif args.command == "load-smogon":
        load_smogon(args.month, args.family or list(smogon.FAMILIES))
    elif args.command == "update-smogon":
        update_smogon(datetime.now(UTC).date())
    elif args.command == "collect-replays":
        collect_replays(args.start, args.end)
    elif args.command == "parse-replays":
        parse_replays(args.reparse)
    elif args.command == "update-replays":
        update_replays()


if __name__ == "__main__":
    main()
