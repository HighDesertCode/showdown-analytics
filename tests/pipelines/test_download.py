from pipelines import download


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return b'{"ok": true}'


def test_fetch_returns_bytes_and_sends_user_agent(monkeypatch):
    requests = []
    monkeypatch.setattr(
        download.urllib.request, "urlopen", lambda request, timeout: requests.append(request) or FakeResponse()
    )

    assert download.fetch("https://example.com/data.json") == b'{"ok": true}'
    assert requests[0].get_header("User-agent") == download.USER_AGENT
