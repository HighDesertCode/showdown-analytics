"""Runs source_file against real tables built from sql/ (see tests/pipelines/conftest.py)."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import psycopg
import pytest

from pipelines import smogon
from pipelines.raw import source_file

WATER = smogon.report_files("chaos", date(2026, 9, 1), ["water"])[1]
RETRIEVED = source_file.RetrievedFile(WATER, b'{"info": {}}', datetime(2026, 10, 27, tzinfo=UTC))
REPUBLISHED = b'{"info": {"republished": true}}'


def test_insert_records_the_file(conn):
    water_id = conn.execute(
        "INSERT INTO reference.type (showdown_id, name) VALUES ('water', 'Water') RETURNING type_id"
    )
    team_type_id = water_id.fetchone()[0]

    source_file_id = source_file.insert(conn, RETRIEVED, team_type_id)

    row = conn.execute(
        "SELECT url, family, report_month, baseline, team_type_id, content_sha256, byte_size"
        " FROM raw.source_file WHERE source_file_id = %s",
        (source_file_id,),
    ).fetchone()
    assert row == (
        RETRIEVED.file.url,
        "chaos",
        RETRIEVED.file.report_month,
        1630,
        team_type_id,
        RETRIEVED.sha256,
        len(RETRIEVED.content),
    )


def test_is_loaded_matches_url_and_content(conn):
    assert not source_file.is_loaded(conn, RETRIEVED)

    source_file.insert(conn, RETRIEVED, None)

    assert source_file.is_loaded(conn, RETRIEVED)
    assert not source_file.is_loaded(conn, replace(RETRIEVED, content=REPUBLISHED))


def test_is_loaded_compares_only_the_latest_version(conn):
    source_file.insert(conn, RETRIEVED, None)
    republished = replace(RETRIEVED, content=REPUBLISHED, retrieved_at=RETRIEVED.retrieved_at + timedelta(days=1))
    source_file.insert(conn, republished, None)
    reverted = replace(RETRIEVED, retrieved_at=RETRIEVED.retrieved_at + timedelta(days=2))

    # The original content matches an older version but not the latest one, so it is loaded again.
    assert not source_file.is_loaded(conn, reverted)
    assert source_file.is_loaded(conn, republished)

    source_file.insert(conn, reverted, None)

    assert source_file.is_loaded(conn, reverted)


def test_missing_urls_lists_files_with_no_recorded_version(conn):
    urls = [file.url for file in smogon.report_files("chaos", date(2026, 9, 1), ["water"])]
    assert source_file.missing_urls(conn, urls) == urls

    # Every version of a URL counts as recorded, whatever its content.
    source_file.insert(conn, RETRIEVED, None)
    source_file.insert(conn, replace(RETRIEVED, retrieved_at=RETRIEVED.retrieved_at + timedelta(days=1)), None)

    assert source_file.missing_urls(conn, urls) == [url for url in urls if url != WATER.url]


def test_insert_rejects_a_second_version_retrieved_at_the_same_time(conn):
    source_file.insert(conn, RETRIEVED, None)

    with pytest.raises(psycopg.errors.UniqueViolation, match="source_file_retrieval_unique"):
        source_file.insert(conn, replace(RETRIEVED, content=REPUBLISHED), None)
