"""Downloads public data files over HTTPS."""

import http.client
import sys
import time
import urllib.error
import urllib.request

USER_AGENT = "showdown-analytics (+https://github.com/HighDesertCode/showdown-analytics)"
# Seconds to wait before each retry, so a download is tried at most three times.
RETRY_WAITS = (5, 15)
# Errors from a download that never succeeded (HTTPError, for any status, is a URLError).
NETWORK_ERRORS = (urllib.error.URLError, TimeoutError, ConnectionError, http.client.IncompleteRead)


def fetch(url: str) -> bytes:
    """Returns the response body as raw bytes, so callers can hash exactly what was downloaded.

    Brief failures (timeouts, dropped connections, 429 and 5xx responses) are retried; anything else,
    such as a 404 for a month Smogon hasn't published, fails at once.
    """
    return _request(url, "GET")


def exists(url: str) -> bool:
    """True if the URL answers a HEAD request, and False on a 404; retries brief failures as `fetch` does."""
    try:
        _request(url, "HEAD")
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return False
        raise
    return True


def _request(url: str, method: str) -> bytes:
    for wait in RETRY_WAITS:
        try:
            return _request_once(url, method)
        except Exception as error:
            if not _is_temporary(error):
                raise
            print(f"Retrying {url} in {wait}s after: {error}", file=sys.stderr)
            time.sleep(wait)
    return _request_once(url, method)


def _request_once(url: str, method: str) -> bytes:
    request = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def _is_temporary(error: Exception) -> bool:
    if isinstance(error, urllib.error.HTTPError):
        return error.code == 429 or error.code >= 500
    return isinstance(error, NETWORK_ERRORS)
