"""Downloads public data files over HTTPS."""

import urllib.request

USER_AGENT = "showdown-analytics (+https://github.com/HighDesertCode/showdown-analytics)"


def fetch(url: str) -> bytes:
    """Returns the response body as raw bytes, so callers can hash exactly what was downloaded."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()
