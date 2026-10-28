"""Runs source_file against real tables built from sql/ (see tests/pipelines/conftest.py)."""

from dataclasses import replace
from datetime import UTC, date, datetime

from pipelines import smogon
from pipelines.raw import source_file

WATER = smogon.report_files("chaos", date(2026, 9, 1), ["water"])[1]
RETRIEVED = source_file.RetrievedFile(WATER, b'{"info": {}}', datetime(2026, 10, 27, tzinfo=UTC))


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
    assert not source_file.is_loaded(conn, replace(RETRIEVED, content=b'{"info": {"republished": true}}'))
