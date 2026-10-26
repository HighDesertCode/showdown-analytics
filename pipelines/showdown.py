"""Fetches and parses Pokémon Showdown's public data files.

Most files come from Showdown's client site. Natures and descriptions are only published in
Showdown's GitHub repository. Files are read into memory and parsed as data, never executed.
"""

import json
import re
import urllib.request

import json5

CLIENT_DATA = "https://play.pokemonshowdown.com/data"
REPO_DATA = "https://raw.githubusercontent.com/smogon/pokemon-showdown/master/data"

SOURCES = {
    "species": f"{CLIENT_DATA}/pokedex.json",
    "moves": f"{CLIENT_DATA}/moves.json",
    "types": f"{CLIENT_DATA}/typechart.js",
    "abilities": f"{CLIENT_DATA}/abilities.js",
    "items": f"{CLIENT_DATA}/items.js",
    "natures": f"{REPO_DATA}/natures.ts",
    "ability_text": f"{REPO_DATA}/text/abilities.ts",
    "item_text": f"{REPO_DATA}/text/items.ts",
    "move_text": f"{REPO_DATA}/text/moves.ts",
}

USER_AGENT = "showdown-analytics (+https://github.com/HighDesertCode/showdown-analytics)"


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def parse(text: str) -> dict:
    """Parses a JSON file, or the object literal assigned in a .js/.ts data file."""
    if text.lstrip().startswith("{"):
        return json.loads(text)
    # Find `= {` rather than the first `{`: TypeScript type annotations can contain braces.
    assignment = re.search(r"=\s*\{", text)
    if assignment is None:
        raise ValueError("No object literal assignment found")
    return json5.loads(text[assignment.end() - 1 : text.rindex("}") + 1])


def to_id(name: str) -> str:
    """Converts a display name to a Showdown ID, matching Showdown's toID (Heavy-Duty Boots -> heavydutyboots)."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def load(name: str) -> dict:
    return parse(fetch(SOURCES[name]))
