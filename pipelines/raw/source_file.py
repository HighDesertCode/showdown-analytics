"""Records each Smogon file in raw.source_file, the provenance every raw row links back to."""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from psycopg import Connection

from pipelines import download
from pipelines.smogon import ReportFile


@dataclass(frozen=True)
class RetrievedFile:
    file: ReportFile
    content: bytes
    retrieved_at: datetime

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()


def retrieve(file: ReportFile) -> RetrievedFile:
    content = download.fetch(file.url)
    return RetrievedFile(file, content, datetime.now(UTC))


def is_loaded(conn: Connection, retrieved: RetrievedFile) -> bool:
    """True if the URL's latest recorded version has the same content.

    Only the latest version counts, so a file that reverts to earlier content is recorded again. Versions are
    ordered as in dbt's stg_source_file, so both agree on which one is current.
    """
    row = conn.execute(
        "SELECT content_sha256 FROM raw.source_file WHERE url = %s"
        " ORDER BY retrieved_at DESC, source_file_id DESC LIMIT 1",
        (retrieved.file.url,),
    ).fetchone()
    return row is not None and row[0] == retrieved.sha256


def missing_urls(conn: Connection, urls: list[str]) -> list[str]:
    """Returns the URLs with no recorded version, in the order given, without downloading anything."""
    rows = conn.execute("SELECT DISTINCT url FROM raw.source_file WHERE url = ANY(%s)", (urls,))
    recorded = {url for (url,) in rows}
    return [url for url in urls if url not in recorded]


def insert(conn: Connection, retrieved: RetrievedFile, team_type_id: int | None) -> int:
    """Records the file and returns its source_file_id."""
    file = retrieved.file
    row = conn.execute(
        """
        INSERT INTO raw.source_file
            (url, family, format, report_month, baseline, team_type_id, content_sha256, byte_size, retrieved_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING source_file_id
        """,
        (
            file.url,
            file.family,
            file.format,
            file.report_month,
            file.baseline,
            team_type_id,
            retrieved.sha256,
            len(retrieved.content),
            retrieved.retrieved_at,
        ),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"Could not record {file.url}")
    return row[0]
