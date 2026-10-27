"""Loads one Smogon report file into the raw schema."""

from psycopg import Connection

from pipelines.raw import chaos, source_file
from pipelines.smogon import ReportFile


def load_file(conn: Connection, file: ReportFile, team_type_id: int | None) -> dict[str, int] | None:
    """Downloads and loads a file; returns the rows inserted per table, or None if it was already loaded.

    Nothing is inserted unless the whole file parses, and the caller commits after each file.
    """
    retrieved = source_file.retrieve(file)
    if source_file.is_loaded(conn, retrieved):
        return None
    try:
        report = chaos.parse(retrieved.content, file)
    except chaos.ChaosFormatError as error:
        raise chaos.ChaosFormatError(f"{file.url}: {error}") from error
    source_file_id = source_file.insert(conn, retrieved, team_type_id)
    return chaos.load(conn, source_file_id, report)
