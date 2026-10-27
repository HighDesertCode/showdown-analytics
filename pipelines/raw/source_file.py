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
    """True if this exact file (same URL and content) is already recorded."""
    row = conn.execute(
        "SELECT EXISTS (SELECT 1 FROM raw.source_file WHERE url = %s AND content_sha256 = %s)",
        (retrieved.file.url, retrieved.sha256),
    ).fetchone()
    return row is not None and row[0]


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
