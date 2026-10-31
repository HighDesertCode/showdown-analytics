import json
from datetime import UTC, datetime

import pytest

from pipelines import replays
from pipelines.replays import Replay, ReplayFormatError, SearchResult

LOG = "|j|☆jago421\n|player|p1|jago421|pokemonranger-gen4|1093\n|win|jago421\n"
REPLAY = {
    "id": "gen9monotype-2703725750",
    "format": "[Gen 9] Monotype",
    "formatid": "gen9monotype",
    "players": ["jago421", "MistyMarill"],
    "log": LOG,
    "uploadtime": 1792817699,
    "views": "15",
    "rating": 1113,
    "private": 0,
    "password": None,
}


def entry(number: int, uploadtime: int) -> dict:
    return {"id": f"gen9monotype-{number}", "uploadtime": uploadtime, "format": "[Gen 9] Monotype"}


def result(number: int, uploadtime: int) -> SearchResult:
    return SearchResult(f"gen9monotype-{number}", datetime.fromtimestamp(uploadtime, UTC))


@pytest.fixture
def waits(monkeypatch):
    """Records each pause between requests instead of sleeping."""
    waits = []
    monkeypatch.setattr(replays.time, "sleep", waits.append)
    return waits


def serve(monkeypatch, responses: dict[str, object]) -> list[str]:
    """Answers each URL with its JSON response; returns the URLs requested, in order."""
    requested = []

    def fetch(url):
        requested.append(url)
        return json.dumps(responses[url]).encode()

    monkeypatch.setattr(replays.download, "fetch", fetch)
    return requested


def test_search_url():
    assert replays.search_url("gen9monotype") == "https://replay.pokemonshowdown.com/search.json?format=gen9monotype"
    assert replays.search_url("gen9monotype", 1792817700) == (
        "https://replay.pokemonshowdown.com/search.json?format=gen9monotype&before=1792817700"
    )


def test_search_pages_back_from_the_oldest_upload_plus_one_second(monkeypatch, waits):
    first = [entry(1000 - n, 2000 - n) for n in range(replays.PAGE_SIZE)]  # uploads 2000 down to 1950
    # The next page repeats the replay uploaded at 1950, which is skipped.
    second = [entry(950, 1950), entry(949, 1949), entry(948, 1948)]
    requested = serve(
        monkeypatch,
        {replays.search_url("gen9monotype"): first, replays.search_url("gen9monotype", 1951): second},
    )

    results = list(replays.search("gen9monotype", start=datetime.fromtimestamp(0, UTC)))

    assert requested == [replays.search_url("gen9monotype"), replays.search_url("gen9monotype", 1951)]
    assert [r.replay_id for r in results] == [f"gen9monotype-{n}" for n in range(1000, 947, -1)]
    assert waits == [replays.REQUEST_GAP, replays.REQUEST_GAP]


def test_search_stops_at_start_without_reading_more_pages(monkeypatch, waits):
    page = [entry(1000 - n, 2000 - n) for n in range(replays.PAGE_SIZE)]
    requested = serve(monkeypatch, {replays.search_url("gen9monotype"): page})

    results = list(replays.search("gen9monotype", start=datetime.fromtimestamp(1998, UTC)))

    assert results == [result(1000, 2000), result(999, 1999), result(998, 1998)]
    assert len(requested) == 1


def test_search_starts_paging_at_the_end(monkeypatch, waits):
    page = [entry(1000, 1999), entry(999, 1998)]
    requested = serve(monkeypatch, {replays.search_url("gen9monotype", 2000): page})

    end = datetime.fromtimestamp(2000, UTC)
    results = list(replays.search("gen9monotype", start=datetime.fromtimestamp(0, UTC), end=end))

    assert results == [result(1000, 1999), result(999, 1998)]
    assert requested == [replays.search_url("gen9monotype", 2000)]


def test_search_stops_when_a_full_page_has_nothing_new(monkeypatch, waits):
    # More than a page of replays uploaded in the same second would otherwise be requested forever.
    page = [entry(1000 - n, 2000) for n in range(replays.PAGE_SIZE)]
    requested = serve(
        monkeypatch,
        {replays.search_url("gen9monotype"): page, replays.search_url("gen9monotype", 2001): page},
    )

    results = list(replays.search("gen9monotype", start=datetime.fromtimestamp(0, UTC)))

    assert len(results) == replays.PAGE_SIZE
    assert len(requested) == 2


def test_parse_search_marks_side_server_replays():
    page = [entry(2, 2000), {"id": "smogtours-gen9monotype-1", "uploadtime": 1999}]

    assert replays.parse_search(json.dumps(page).encode()) == [
        result(2, 2000),
        SearchResult("smogtours-gen9monotype-1", datetime.fromtimestamp(1999, UTC), "smogtours"),
    ]


@pytest.mark.parametrize(
    "page",
    [
        {"id": "gen9monotype-1"},
        ["gen9monotype-1"],
        [{"uploadtime": 2000}],
        [{"id": "../secret", "uploadtime": 2000}],
        [{"id": "gen9monotype-1", "uploadtime": "2000"}],
        [{"id": "gen9monotype-1", "uploadtime": True}],
    ],
)
def test_parse_search_rejects_unexpected_shapes(page):
    with pytest.raises(ReplayFormatError):
        replays.parse_search(json.dumps(page).encode())


def test_fetch_replay(monkeypatch, waits):
    requested = serve(monkeypatch, {replays.replay_url("gen9monotype-2703725750"): REPLAY})

    replay = replays.fetch_replay("gen9monotype-2703725750")

    assert requested == ["https://replay.pokemonshowdown.com/gen9monotype-2703725750.json"]
    assert replay == Replay(
        replay_id="gen9monotype-2703725750",
        format_id="gen9monotype",
        format="[Gen 9] Monotype",
        players=("jago421", "MistyMarill"),
        rating=1113,
        uploaded_at=datetime(2026, 10, 24, 4, 54, 59, tzinfo=UTC),
        log=LOG,
    )
    assert waits == [replays.REQUEST_GAP]


def test_parse_replay_keeps_utf8_names():
    replay = replays.parse_replay(json.dumps(REPLAY, ensure_ascii=False).encode(), "gen9monotype-2703725750")

    assert replay.log.startswith("|j|☆jago421")


def test_parse_replay_allows_an_unrated_battle():
    body = json.dumps(REPLAY | {"rating": None}).encode()

    assert replays.parse_replay(body, "gen9monotype-2703725750").rating is None


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"id": "gen9monotype-1"}, "has id"),
        ({"private": 1}, "not public"),
        ({"password": "abc"}, "not public"),
        ({"formatid": "Gen 9 Monotype"}, "has formatid"),
        ({"format": ""}, "has format"),
        ({"players": ["jago421"]}, "has players"),
        ({"players": ["jago421", None]}, "has players"),
        ({"rating": -1}, "has rating"),
        ({"rating": "1113"}, "has rating"),
        ({"log": ""}, "no log"),
        ({"uploadtime": None}, "has uploadtime"),
    ],
)
def test_parse_replay_rejects_unexpected_shapes(changes, message):
    with pytest.raises(ReplayFormatError, match=message):
        replays.parse_replay(json.dumps(REPLAY | changes).encode(), "gen9monotype-2703725750")


@pytest.mark.parametrize("body", [b"<html>Not found</html>", b"\xff\xfe", b"[]"])
def test_parse_replay_rejects_responses_that_are_not_a_replay(body):
    with pytest.raises(ReplayFormatError):
        replays.parse_replay(body, "gen9monotype-2703725750")
