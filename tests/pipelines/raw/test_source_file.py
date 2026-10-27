import hashlib
from datetime import UTC, date, datetime

from pipelines import smogon
from pipelines.raw import source_file

WATER = smogon.report_files("chaos", date(2026, 9, 1), ["water"])[1]
RETRIEVED = source_file.RetrievedFile(WATER, b'{"info": {}}', datetime(2026, 10, 27, tzinfo=UTC))


def test_sha256_hashes_the_exact_bytes():
    assert RETRIEVED.sha256 == hashlib.sha256(b'{"info": {}}').hexdigest()


def test_retrieve_downloads_the_file_url(monkeypatch):
    fetched = []
    monkeypatch.setattr(source_file.download, "fetch", lambda url: fetched.append(url) or b"{}")

    retrieved = source_file.retrieve(WATER)

    assert fetched == [WATER.url]
    assert retrieved.content == b"{}"
    assert retrieved.retrieved_at.tzinfo is UTC
