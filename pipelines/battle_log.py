"""Parses a Pokémon Showdown battle log into the facts it states about the battle, its players, and their teams.

A log is one protocol message per line, `|type|arg|arg...`. Every line type must be known: header types are read
here, game event types by pipelines.battle_events, and chat and display types are skipped. Anything else raises
ReplayFormatError, so a protocol change is noticed rather than silently dropped.
"""

import html
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from pipelines import battle_events
from pipelines.battle_events import Event, same_species
from pipelines.replays import ReplayFormatError

# Lines that describe the battle as a whole.
HEADER_TYPES = {
    "", "t:", "turn", "upkeep", "player", "teamsize", "gametype", "gen", "tier", "rule", "rated", "clearpoke", "poke",
    "teampreview", "start", "win", "tie", "raw", "-message",
}  # fmt: skip
# Game events, parsed into raw.battle_event.
EVENT_TYPES = {
    "move", "switch", "drag", "replace", "detailschange", "faint", "cant", "-damage", "-heal", "-sethp", "-status",
    "-curestatus", "-boost", "-unboost", "-setboost", "-clearboost", "-clearallboost", "-clearnegativeboost",
    "-weather", "-fieldstart", "-fieldend", "-fieldactivate", "-sidestart", "-sideend", "-swapsideconditions",
    "-start", "-end", "-ability", "-item", "-enditem", "-activate", "-singleturn", "-singlemove", "-prepare",
    "-mustrecharge", "-hitcount", "-crit", "-supereffective", "-resisted", "-immune", "-miss", "-fail",
    "-formechange", "-transform", "-terastallize", "-mega", "-copyboost", "-swapboost", "-invertboost", "-block",
    "-endability", "-nothing",
}  # fmt: skip
# Chat, joins and leaves, timers, and display-only lines; they stay in raw.replay.log.
SKIPPED_TYPES = {"j", "l", "n", "c", "html", "uhtml", "badge", "inactive", "inactiveoff", "-hint", "-anim"}

SIDES = ("p1", "p2")
RATING_CHANGE = re.compile(r"^(?P<player>.+)'s rating: (?P<before>\d+) → <strong>(?P<after>\d+)</strong>")
POKEMON = re.compile(r"^(?P<side>p[12])[a-z]?: (?P<nickname>.+)$")


@dataclass(frozen=True)
class Side:
    side: str
    player: str
    elo_before: int | None
    elo_after: int | None
    result: str  # win, loss, or tie


@dataclass(frozen=True)
class PreviewPokemon:
    side: str
    slot: int
    species: str  # As previewed; a "-*" suffix hides the form until it switches in.
    nickname: str | None  # The name the log uses for it, or None if it never switched in.


@dataclass(frozen=True)
class Battle:
    replay_id: str
    rated: bool
    started_at: datetime
    ended_at: datetime
    turns: int
    winner: str | None  # None for a tie.
    ended_by: str  # knockout, forfeit, inactivity, or tie
    rules: tuple[str, ...]
    sides: tuple[Side, Side]
    team: tuple[PreviewPokemon, ...]
    events: tuple[Event, ...]


def parse(log: str, replay_id: str) -> Battle:
    raw_lines = [line for line in log.splitlines() if line]
    lines = [line.split("|")[1:] for line in raw_lines]
    players: dict[str, str] = {}
    player_elo: dict[str, int | None] = {}
    rating_changes: dict[str, tuple[int, int]] = {}
    preview: dict[str, list[str]] = {side: [] for side in SIDES}
    team_size: dict[str, int] = {}
    times: list[datetime] = []
    rules: list[str] = []
    messages: list[str] = []
    rated = False
    turns = 0
    winner_name: str | None = None
    tie = False
    for parts in lines:
        kind = parts[0] if parts else ""
        args = parts[1:]
        if kind in EVENT_TYPES or kind in SKIPPED_TYPES:
            continue
        if kind not in HEADER_TYPES:
            raise ReplayFormatError(f"{replay_id} has an unknown line type {kind!r}")
        if kind == "t:":
            times.append(datetime.fromtimestamp(_integer(args, replay_id, kind), UTC))
        elif kind == "turn":
            turns = _integer(args, replay_id, kind)
        elif kind == "player" and len(args) >= 2 and args[1]:
            side = _side(args[0], replay_id)
            if side not in players:  # Later lines repeat it, or mark a player leaving with an empty name.
                players[side] = args[1]
                player_elo[side] = int(args[3]) if len(args) > 3 and args[3].isdigit() else None
        elif kind == "teamsize":
            team_size[_side(args[0], replay_id)] = int(args[1])
        elif kind == "gametype" and args != ["singles"]:
            raise ReplayFormatError(f"{replay_id} is a {args} battle, not singles")
        elif kind == "gen" and args != ["9"]:
            raise ReplayFormatError(f"{replay_id} is from generation {args}, not 9")
        elif kind == "rule":
            rules.append(args[0].split(": ", 1)[0])
        elif kind == "rated":
            rated = args in ([], [""])  # Tournament battles say "Tournament battle" and aren't rated.
        elif kind == "poke":
            preview[_side(args[0], replay_id)].append(args[1].split(", ")[0])
        elif kind == "win":
            winner_name = args[0]
        elif kind == "tie":
            tie = True
        elif kind == "raw" and args and (change := RATING_CHANGE.match(html.unescape(args[0]))):
            rating_changes[change["player"]] = (int(change["before"]), int(change["after"]))
        elif kind == "-message" and args:
            messages.append(args[0])

    if set(players) != set(SIDES):
        raise ReplayFormatError(f"{replay_id} names players for {sorted(players)}")
    if not times:
        raise ReplayFormatError(f"{replay_id} has no timestamps")
    sides_by_name = {name: side for side, name in players.items()}
    if tie == (winner_name is not None):
        raise ReplayFormatError(f"{replay_id} has neither a single winner nor a tie")
    if winner_name is not None and winner_name not in sides_by_name:
        raise ReplayFormatError(f"{replay_id} has winner {winner_name!r}, who isn't a player")
    winner = None if winner_name is None else sides_by_name[winner_name]
    for side in SIDES:
        if side in team_size and len(preview[side]) != team_size[side]:
            raise ReplayFormatError(f"{replay_id} previews {len(preview[side])} Pokémon for {side}")

    team = tuple(
        PreviewPokemon(side, slot, species, _nickname(lines, side, species, preview[side]))
        for side in SIDES
        for slot, species in enumerate(preview[side], start=1)
    )
    nicknames: dict[tuple[str, str], tuple[str, ...]] = {}
    for pokemon in team:
        if pokemon.nickname:
            key = (pokemon.side, pokemon.nickname)
            nicknames[key] = (*nicknames.get(key, ()), pokemon.species)
    return Battle(
        replay_id=replay_id,
        rated=rated,
        started_at=times[0],
        ended_at=times[-1],
        turns=turns,
        winner=winner,
        ended_by=_ended_by(messages, players, tie),
        rules=tuple(rules),
        sides=(
            _side_result("p1", players, player_elo, rating_changes, winner),
            _side_result("p2", players, player_elo, rating_changes, winner),
        ),
        team=team,
        events=battle_events.parse(raw_lines, nicknames, replay_id, EVENT_TYPES),
    )


def _ended_by(messages: list[str], players: dict[str, str], tie: bool) -> str:
    if tie:
        return "tie"
    for name in players.values():
        if f"{name} forfeited." in messages:
            return "forfeit"
        if f"{name} lost due to inactivity." in messages:
            return "inactivity"
    return "knockout"


def _side_result(
    side: str,
    players: dict[str, str],
    player_elo: dict[str, int | None],
    rating_changes: dict[str, tuple[int, int]],
    winner: str | None,
) -> Side:
    # The rating change is this battle's own before and after. The player line's rating is from when the battle
    # started, which differs if another of the player's battles ended in between, so it's only the fallback.
    elo_before, elo_after = rating_changes.get(players[side], (player_elo[side], None))
    result = "tie" if winner is None else "win" if winner == side else "loss"
    return Side(side, players[side], elo_before, elo_after, result)


def _nickname(lines: list[list[str]], side: str, species: str, team: list[str]) -> str | None:
    """The name of the first Pokémon to enter for `side` as this species or one of its forms.

    A Pokémon entering as another previewed species is never this one, even if its name starts the same way
    (Porygon-Z is not a form of Porygon).
    """
    for parts in lines:
        if len(parts) >= 3 and parts[0] in ("switch", "drag", "replace"):
            match = POKEMON.match(parts[1])
            entered = parts[2].split(", ")[0]
            if (
                match
                and match["side"] == side
                and (entered == species or entered not in team)
                and same_species(species, entered)
            ):
                return match["nickname"]
    return None


def _side(value: str, replay_id: str) -> str:
    if value not in SIDES:
        raise ReplayFormatError(f"{replay_id} has side {value!r}")
    return value


def _integer(args: list[str], replay_id: str, kind: str) -> int:
    if not args or not args[0].isdigit():
        raise ReplayFormatError(f"{replay_id} has a {kind} line with {args!r}")
    return int(args[0])
