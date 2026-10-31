"""Finds and downloads public Pokémon Showdown replays.

Showdown's replay server lists a format's public replays newest first at search.json, 51 to a page; each later page
starts before an upload time (in Unix seconds). Each replay's JSON at /{id}.json holds its metadata and battle log.
"""

import json
import math
import re
import time
import urllib.parse
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime

from pipelines import download

REPLAY_URL = "https://replay.pokemonshowdown.com"
FORMAT_ID = "gen9monotype"
PAGE_SIZE = 51
# Seconds between requests, to keep the load on Showdown's replay server modest.
REQUEST_GAP = 1.0
# A main-server replay is "<format>-<number>"; side servers prefix their own name (e.g. "smogtours-").
REPLAY_ID = re.compile(r"^[a-z0-9]+-[0-9]+$")
SIDE_SERVER_REPLAY_ID = re.compile(r"^([a-z0-9]+)-[a-z0-9]+-[0-9]+$")
FORMAT_ID_PATTERN = re.compile(r"^[a-z0-9]+$")


class ReplayFormatError(ValueError):
    """A search page or replay does not have the shape this module expects."""


@dataclass(frozen=True)
class SearchResult:
    replay_id: str
    uploaded_at: datetime
    server: str | None = None  # The side server it was played on, or None for Showdown's main server.


@dataclass(frozen=True)
class Replay:
    """A public replay as published, matching raw.replay's columns."""

    replay_id: str
    format_id: str
    format: str
    players: tuple[str, str]
    rating: int | None  # None for an unrated battle.
    uploaded_at: datetime
    log: str


def search_url(format_id: str, before: int | None = None) -> str:
    query = {"format": format_id} if before is None else {"format": format_id, "before": before}
    return f"{REPLAY_URL}/search.json?{urllib.parse.urlencode(query)}"


def replay_url(replay_id: str) -> str:
    return f"{REPLAY_URL}/{replay_id}.json"


def search(format_id: str, start: datetime, end: datetime | None = None) -> Iterator[SearchResult]:
    """Yields the public replays uploaded at or after `start` and before `end` (or now), newest first, reading only
    the pages it needs.

    Each later page starts one second after the previous page's oldest upload, so replays uploaded in the same second
    as a page boundary aren't missed; replays already yielded are skipped.
    """
    seen: set[str] = set()
    before = None if end is None else math.ceil(end.timestamp())
    while True:
        page = parse_search(_fetch(search_url(format_id, before)))
        new = [result for result in page if result.replay_id not in seen]
        for result in new:
            if result.uploaded_at < start:
                return
            seen.add(result.replay_id)
            yield result
        if len(page) < PAGE_SIZE or not new:
            return
        before = int(page[-1].uploaded_at.timestamp()) + 1


def fetch_replay(replay_id: str) -> Replay:
    """Downloads one replay; raises ReplayFormatError if it isn't public or has an unexpected shape."""
    return parse_replay(_fetch(replay_url(replay_id)), replay_id)


def parse_search(body: bytes) -> list[SearchResult]:
    page = _json(body)
    if not isinstance(page, list):
        raise ReplayFormatError("Search page is not a list")
    return [_search_result(entry) for entry in page]


def parse_replay(body: bytes, replay_id: str) -> Replay:
    replay = _json(body)
    if not isinstance(replay, dict):
        raise ReplayFormatError(f"{replay_id} is not an object")
    if _replay_id(replay) != replay_id:
        raise ReplayFormatError(f"{replay_id} has id {replay.get('id')!r}")
    if replay.get("private") != 0 or replay.get("password") is not None:
        raise ReplayFormatError(f"{replay_id} is not public")
    format_id, name, players = replay.get("formatid"), replay.get("format"), replay.get("players")
    rating, log = replay.get("rating"), replay.get("log")
    if not isinstance(format_id, str) or not FORMAT_ID_PATTERN.match(format_id):
        raise ReplayFormatError(f"{replay_id} has formatid {format_id!r}")
    if not isinstance(name, str) or not name:
        raise ReplayFormatError(f"{replay_id} has format {name!r}")
    if not isinstance(players, list) or len(players) != 2 or not all(isinstance(p, str) and p for p in players):
        raise ReplayFormatError(f"{replay_id} has players {players!r}")
    if rating is not None and (type(rating) is not int or rating < 0):
        raise ReplayFormatError(f"{replay_id} has rating {rating!r}")
    if not isinstance(log, str) or not log:
        raise ReplayFormatError(f"{replay_id} has no log")
    return Replay(replay_id, format_id, name, (players[0], players[1]), rating, _uploaded_at(replay), log)


def _fetch(url: str) -> bytes:
    time.sleep(REQUEST_GAP)
    return download.fetch(url)


def _json(body: bytes) -> object:
    try:
        return json.loads(body)
    except ValueError as error:  # Also covers bytes that aren't UTF-8.
        raise ReplayFormatError(f"Response is not JSON: {error}") from error


def _search_result(entry: object) -> SearchResult:
    """Search lists side-server replays too, so their IDs are accepted here and marked with the server."""
    if not isinstance(entry, dict):
        raise ReplayFormatError(f"Unexpected search result {entry!r}")
    replay_id = entry.get("id")
    side_server = SIDE_SERVER_REPLAY_ID.match(replay_id) if isinstance(replay_id, str) else None
    if side_server:
        return SearchResult(side_server.string, _uploaded_at(entry), side_server.group(1))
    return SearchResult(_replay_id(entry), _uploaded_at(entry))


def _replay_id(entry: object) -> str:
    replay_id = entry.get("id") if isinstance(entry, dict) else None
    if not isinstance(replay_id, str) or not REPLAY_ID.match(replay_id):
        raise ReplayFormatError(f"Unexpected replay id {replay_id!r}")
    return replay_id


def _uploaded_at(entry: dict) -> datetime:
    uploadtime = entry.get("uploadtime")
    if type(uploadtime) is not int or uploadtime <= 0:
        raise ReplayFormatError(f"{entry.get('id')} has uploadtime {uploadtime!r}")
    return datetime.fromtimestamp(uploadtime, UTC)
