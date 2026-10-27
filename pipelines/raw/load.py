"""Loads one Smogon report file into the raw schema."""

from collections.abc import Callable

from psycopg import Connection

from pipelines.raw import chaos, leads, metagame, source_file, usage
from pipelines.raw.common import Report, ReportFormatError
from pipelines.smogon import ReportFile

# Each family's parser. Parsers that only need the file's content ignore the ReportFile.
PARSERS: dict[str, Callable[[bytes, ReportFile], Report]] = {
    "chaos": chaos.parse,
    "usage": lambda content, file: usage.parse(content),
    "leads": lambda content, file: leads.parse(content),
    "metagame": lambda content, file: metagame.parse(content),
}


def load_file(conn: Connection, file: ReportFile, team_type_id: int | None) -> dict[str, int] | None:
    """Downloads and loads a file; returns the rows inserted per table, or None if it was already loaded.

    Nothing is inserted unless the whole file parses, and the caller commits after each file.
    """
    retrieved = source_file.retrieve(file)
    if source_file.is_loaded(conn, retrieved):
        return None
    try:
        report = PARSERS[file.family](retrieved.content, file)
    except ReportFormatError as error:
        raise ReportFormatError(f"{file.url}: {error}") from error
    source_file_id = source_file.insert(conn, retrieved, team_type_id)
    return report.load(conn, source_file_id)
