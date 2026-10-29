import urllib.error
from email.message import Message

import pytest

from pipelines import download

URL = "https://example.com/data.json"


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return b'{"ok": true}'


def http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(URL, code, "error", Message(), None)


@pytest.fixture
def waits(monkeypatch):
    """Records each retry wait instead of sleeping."""
    waits = []
    monkeypatch.setattr(download.time, "sleep", waits.append)
    return waits


def respond_with(monkeypatch, *outcomes):
    """Makes each download attempt raise or return the next outcome; returns the requests made."""
    requests = []
    remaining = list(outcomes)

    def urlopen(request, timeout):
        requests.append(request)
        outcome = remaining.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(download.urllib.request, "urlopen", urlopen)
    return requests


def test_fetch_returns_bytes_and_sends_user_agent(monkeypatch, waits):
    requests = respond_with(monkeypatch, FakeResponse())

    assert download.fetch(URL) == b'{"ok": true}'
    assert requests[0].get_header("User-agent") == download.USER_AGENT
    assert waits == []


def test_fetch_retries_a_server_error(monkeypatch, waits):
    requests = respond_with(monkeypatch, http_error(503), FakeResponse())

    assert download.fetch(URL) == b'{"ok": true}'
    assert len(requests) == 2
    assert waits == [5]


def test_fetch_raises_a_missing_file_at_once(monkeypatch, waits):
    requests = respond_with(monkeypatch, http_error(404))

    with pytest.raises(urllib.error.HTTPError, match="404"):
        download.fetch(URL)
    assert len(requests) == 1
    assert waits == []


def test_fetch_raises_the_last_error_after_three_tries(monkeypatch, waits):
    requests = respond_with(monkeypatch, TimeoutError("first"), TimeoutError("second"), TimeoutError("third"))

    with pytest.raises(TimeoutError, match="third"):
        download.fetch(URL)
    assert len(requests) == 3
    assert waits == [5, 15]
