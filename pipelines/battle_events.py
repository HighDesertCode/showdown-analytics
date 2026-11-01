"""Parses the game events in a battle log into raw.battle_event rows, one per event line, in log order.

Each row keeps its log line. HP is a percentage of max HP, as the log shows it. An effect is linked (caused_by) to the
move it happened during, or to the hazard that caused it on switch-in; the only cause the parser deduces rather than
reads is poisoning on switch-in, which the log doesn't attribute, from Toxic Spikes on that side (source_inferred).

A Pokémon with Illusion (Zoroark) enters disguised as another on its team, and the log names it as that Pokémon until
a `replace` line reveals it. The reveal states who it was all along, so the events since it switched in are credited
to it then. A disguise that's never revealed leaves its events with the Pokémon it impersonated, as the log states.

Teammates can share a nickname, so a Pokémon entering is told apart by the species the log shows, and a reference with a
position ("p1a: Name") is the active Pokémon. A reference without one ("p1: Name") to a shared nickname raises.
"""

import dataclasses
import re
from collections.abc import Sequence
from dataclasses import dataclass

from pipelines.replays import ReplayFormatError

POKEMON = re.compile(r"^(?P<side>p[12])(?P<position>[a-z]?): (?P<nickname>.+)$")
TAG = re.compile(r"^\[(?P<name>[a-z]+)\] ?(?P<value>.*)$")
# Prefixes that only say what kind of effect a name is, e.g. "move: Toxic Spikes".
PREFIXES = ("move: ", "ability: ", "item: ")
# HP percentages at a health bar color boundary, and the colors the log may add to them (green, yellow, red).
BAR_BOUNDARIES = {"50": ("g", "y"), "20": ("y", "r")}
# Lines that end the current move's effects: the blank line before end-of-turn effects, and the next turn.
MOVE_ENDS = {"", "upkeep", "turn"}
# Event names for lines whose second argument is the Pokémon they affect.
TARGETED = {"-miss": "miss", "-transform": "transform", "-copyboost": "copy boosts", "-swapboost": "swap boosts"}
# Event names for lines that need no special handling: the event name, and whether the first argument is a Pokémon.
SIMPLE = {
    "-curestatus": ("cure status", True),
    "-clearboost": ("clear boosts", True),
    "-clearallboost": ("clear all boosts", False),
    "-clearnegativeboost": ("clear negative boosts", True),
    "-fieldstart": ("field start", False),
    "-fieldend": ("field end", False),
    "-fieldactivate": ("field activate", False),
    "-start": ("start", True),
    "-end": ("end", True),
    "-ability": ("ability", True),
    "-item": ("item", True),
    "-enditem": ("item removed", True),
    "-activate": ("activate", True),
    "-singleturn": ("single turn", True),
    "-singlemove": ("single move", True),
    "-prepare": ("prepare", True),
    "-mustrecharge": ("must recharge", True),
    "-hitcount": ("hit count", True),
    "-crit": ("critical hit", True),
    "-supereffective": ("super effective", True),
    "-resisted": ("resisted", True),
    "-immune": ("immune", True),
    "-fail": ("fail", True),
    "-terastallize": ("terastallize", True),
    "-mega": ("mega", True),
    "-invertboost": ("invert boosts", True),
    "-block": ("block", True),
    "-endability": ("ability suppressed", True),
    "-nothing": ("nothing", False),
    "cant": ("cant", True),
}


@dataclass(frozen=True)
class Event:
    seq: int
    turn: int
    side: str | None
    pokemon: str | None  # The species shown at team preview, so events join to raw.battle_pokemon.
    event: str
    detail: str | None = None
    target_side: str | None = None
    target_pokemon: str | None = None
    damage_percent: int | None = None
    hp_after_percent: int | None = None
    healed_percent: int | None = None
    caused_by_seq: int | None = None
    source: str | None = None
    source_inferred: bool = False
    log_line: str = ""


class _Parser:
    def __init__(self, team: dict[tuple[str, str], tuple[str, ...]], replay_id: str):
        self.team = team  # (side, nickname) -> the previewed species with that nickname
        self.replay_id = replay_id
        self.events: list[Event] = []
        self.turn = 0
        self.move: int | None = None  # seq of the move whose effects are being logged
        self.hp: dict[tuple[str, str], int] = {}
        self.conditions: dict[str, dict[str, int]] = {"p1": {}, "p2": {}}  # side -> condition -> seq that set it
        self.entering: dict[str, str] = {}  # side -> Pokémon that switched in, until the next move or turn end
        # side -> the active Pokémon's switch-in seq, and its HP before then, in case Illusion was disguising it
        self.switched_in: dict[str, tuple[int, int | None]] = {}
        self.active: dict[str, str] = {}  # side -> the active Pokémon, as the log names it (Illusion's disguise)

    def error(self, message: str) -> ReplayFormatError:
        return ReplayFormatError(f"{self.replay_id} turn {self.turn}: {message}")

    def pokemon(self, ref: str) -> tuple[str, str]:
        match = POKEMON.match(ref)
        if not match or (match["side"], match["nickname"]) not in self.team:
            raise self.error(f"unknown Pokémon {ref!r}")
        side, species = match["side"], self.team[(match["side"], match["nickname"])]
        if len(species) == 1:
            return side, species[0]
        if match["position"] and self.active.get(side) in species:
            return side, self.active[side]
        raise self.error(f"{ref!r} could be any of {', '.join(species)}")

    def entered(self, ref: str, details: str) -> tuple[str, str]:
        """The Pokémon that switches in or is revealed, told apart from teammates sharing its nickname by species."""
        match = POKEMON.match(ref)
        if not match or (match["side"], match["nickname"]) not in self.team:
            raise self.error(f"unknown Pokémon {ref!r}")
        side, candidates, shown = match["side"], self.team[(match["side"], match["nickname"])], _species(details)
        matches = [shown] if shown in candidates else [c for c in candidates if same_species(c, shown)]
        if len(matches) != 1:
            raise self.error(f"{ref!r} enters as {shown}, which isn't one previewed Pokémon")
        return side, matches[0]

    def add(self, line: str, side: str | None, pokemon: str | None, event: str, **values) -> int:
        values.setdefault("caused_by_seq", self.move)
        seq = len(self.events) + 1
        self.events.append(Event(seq, self.turn, side, pokemon, event, log_line=line, **values))
        return seq

    def source(self, tags: dict[str, str]) -> str | None:
        if "from" not in tags:
            return None
        if "of" not in tags:
            return tags["from"]
        side, pokemon = self.pokemon(tags["of"])
        return f"{tags['from']} ({side} {pokemon})"

    def hp_value(self, text: str) -> int:
        value = text.split(" ")[0]
        if value == "0":
            return 0
        current, _, maximum = value.partition("/")
        # Since late April 2026, HP that rounds to a health bar color boundary carries the bar's color, e.g. "50/100g"
        # for just over half; the color stays in the log line.
        if current in BAR_BOUNDARIES and maximum[3:] in BAR_BOUNDARIES[current]:
            maximum = maximum[:3]
        if maximum != "100" or not current.isdigit() or int(current) > 100:
            raise self.error(f"unexpected HP {text!r}")
        return int(current)

    def change_hp(self, key: tuple[str, str], text: str) -> tuple[int, int]:
        if key not in self.hp:
            raise self.error(f"{key[0]} {key[1]} changes HP before entering")
        before, after = self.hp[key], self.hp_value(text)
        self.hp[key] = after
        return before, after

    def line(self, line: str) -> None:
        parts = line.split("|")[1:]
        kind = parts[0] if parts else ""
        args = [arg for arg in parts[1:] if not TAG.match(arg)]
        tags = {match["name"]: match["value"] for arg in parts[1:] if (match := TAG.match(arg))}
        if kind in MOVE_ENDS:
            self.move = None
            self.entering = {}
            if kind == "turn":
                self.turn = int(args[0])
            return
        if kind == "move":
            side, pokemon = self.pokemon(args[0])
            target = self.pokemon(args[2]) if len(args) > 2 and args[2] else (None, None)
            self.move = None
            self.entering = {}
            self.move = self.add(
                line, side, pokemon, "move", detail=args[1], target_side=target[0], target_pokemon=target[1],
                source=self.source(tags),
            )  # fmt: skip
        elif kind in ("switch", "drag"):
            side, pokemon = self.entered(args[0], args[1])
            hp_before = self.hp.get((side, pokemon))
            self.hp[(side, pokemon)] = self.hp_value(args[2])
            self.entering[side] = pokemon
            self.active[side] = pokemon
            seq = self.add(line, side, pokemon, kind, detail=_species(args[1]),
                           hp_after_percent=self.hp[(side, pokemon)], source=self.source(tags))  # fmt: skip
            self.switched_in[side] = (seq, hp_before)
        elif kind == "replace":
            self.reveal(line, args, tags)
        elif kind in ("detailschange", "-formechange"):
            side, pokemon = self.pokemon(args[0])
            self.add(line, side, pokemon, "form", detail=_species(args[1]), source=self.source(tags))
        elif kind == "faint":
            side, pokemon = self.pokemon(args[0])
            # Some faints have no damage line before them (Destiny Bond, Perish Song), and Revival Blessing heals
            # from zero.
            self.hp[(side, pokemon)] = 0
            self.add(line, side, pokemon, "faint")
        elif kind in ("-damage", "-heal", "-sethp"):
            self.hp_line(line, kind, args, tags)
        elif kind == "-status":
            self.status(line, args, tags)
        elif kind in ("-boost", "-unboost", "-setboost"):
            side, pokemon = self.pokemon(args[0])
            sign = {"-boost": "+", "-unboost": "-", "-setboost": "="}[kind]
            self.add(line, side, pokemon, "boost", detail=f"{sign}{args[2]} {args[1]}", source=self.source(tags))
        elif kind == "-weather":
            event = "weather continues" if "upkeep" in tags else "weather ended" if args[0] == "none" else "weather"
            self.add(line, None, None, event, detail=None if args[0] == "none" else args[0], source=self.source(tags))
        elif kind in ("-sidestart", "-sideend"):
            side = _side_of(args[0])
            condition = _clean(args[1])
            if kind == "-sidestart":
                self.conditions[side][condition] = self.add(line, side, None, "side start", detail=condition)
            else:
                self.conditions[side].pop(condition, None)
                self.add(line, side, None, "side end", detail=condition, source=self.source(tags))
        elif kind == "-swapsideconditions":
            self.conditions = {"p1": self.conditions["p2"], "p2": self.conditions["p1"]}
            self.add(line, None, None, "swap side conditions")
        elif kind in TARGETED:
            side, pokemon = self.pokemon(args[0])
            target = self.pokemon(args[1]) if len(args) > 1 and args[1] else (None, None)
            detail = args[2] if len(args) > 2 else None  # The stats Power Swap and Guard Swap exchange.
            self.add(line, side, pokemon, TARGETED[kind], detail=detail, target_side=target[0],
                     target_pokemon=target[1], source=self.source(tags))  # fmt: skip
        elif kind in SIMPLE:
            event, has_pokemon = SIMPLE[kind]
            side, pokemon = self.pokemon(args[0]) if has_pokemon else (None, None)
            target = self.pokemon(tags["of"]) if "of" in tags and "from" not in tags else (None, None)
            names = args[1:] if has_pokemon else args
            detail = " ".join(_clean(name) for name in names if name) or None
            self.add(line, side, pokemon, event, detail=detail, target_side=target[0], target_pokemon=target[1],
                     source=self.source(tags))  # fmt: skip
        else:
            raise self.error(f"no event handling for {kind!r}")

    def reveal(self, line: str, args: list[str], tags: dict[str, str]) -> None:
        """Credits the events since the disguised switch-in to the Pokémon an Illusion was hiding."""
        side, pokemon = self.entered(args[0], args[1])
        if side not in self.switched_in:
            raise self.error(f"{side} {pokemon} is revealed before anything switched in")
        disguise = self.active[side]
        if disguise == pokemon:
            raise self.error(f"{side} {pokemon} is revealed but wasn't disguised")
        switch_seq, hp_before = self.switched_in[side]
        for index in range(switch_seq - 1, len(self.events)):
            event, changes = self.events[index], {}
            if event.side == side and event.pokemon == disguise:
                changes["pokemon"] = pokemon
            if event.target_side == side and event.target_pokemon == disguise:
                changes["target_pokemon"] = pokemon
            if changes:
                self.events[index] = dataclasses.replace(event, **changes)
        self.hp[(side, pokemon)] = self.hp.pop((side, disguise))
        if hp_before is not None:
            self.hp[(side, disguise)] = hp_before
        if self.entering.get(side) == disguise:
            self.entering[side] = pokemon
        self.active[side] = pokemon
        self.add(line, side, pokemon, "replace", detail=_species(args[1]), source=self.source(tags))

    def hp_line(self, line: str, kind: str, args: list[str], tags: dict[str, str]) -> None:
        if len(args) != 2:  # One Pokémon per line; Pain Split writes a line for each.
            raise self.error(f"{kind} line with {len(args)} arguments")
        side, pokemon = self.pokemon(args[0])
        before, after = self.change_hp((side, pokemon), args[1])
        if (kind == "-damage" and after > before) or (kind == "-heal" and after < before):
            raise self.error(f"{kind} takes {side} {pokemon} from {before} to {after}")
        values = {"source": self.source(tags)}
        # Damage from a hazard on entry is caused by the move that set it, whatever move is being logged.
        if (hazard := self.conditions[side].get(tags.get("from", ""))) is not None:
            values["caused_by_seq"] = hazard
        event = {"-damage": "damage", "-heal": "heal", "-sethp": "set hp"}[kind]
        self.add(
            line, side, pokemon, event, hp_after_percent=after,
            damage_percent=before - after if after < before else None,
            healed_percent=after - before if after > before else None, **values,
        )  # fmt: skip

    def status(self, line: str, args: list[str], tags: dict[str, str]) -> None:
        side, pokemon = self.pokemon(args[0])
        values: dict = {"detail": args[1], "source": self.source(tags)}
        hazard = self.conditions[side].get("Toxic Spikes")
        # The log doesn't say why a Pokémon is poisoned as it enters; Toxic Spikes on its side is the only cause.
        entering = self.entering.get(side) == pokemon
        if "from" not in tags and entering and args[1] in ("psn", "tox") and hazard is not None:
            values.update(caused_by_seq=hazard, source="Toxic Spikes", source_inferred=True)
        self.add(line, side, pokemon, "status", **values)


def parse(
    lines: Sequence[str], team: dict[tuple[str, str], tuple[str, ...]], replay_id: str, event_types: set[str]
) -> tuple[Event, ...]:
    """Parses the lines whose type is in `event_types`, and the turn and move boundaries between them."""
    parser = _Parser(team, replay_id)
    for line in lines:
        parts = line.split("|")[1:]
        kind = parts[0] if parts else ""
        if kind in event_types or kind in MOVE_ENDS:
            parser.line(line)
    return tuple(parser.events)


def same_species(previewed: str, entered: str) -> bool:
    """True if a Pokémon that entered as `entered` is the one previewed as `previewed`.

    It can enter in another form (Terapagos as Terapagos-Terastal, a hit Mimikyu as Mimikyu-Busted), and preview
    hides some forms ("Urshifu-*"). Species Clause allows one Pokémon per base species, so matching it is unambiguous.
    """
    base = previewed.removesuffix("-*")
    return entered == base or entered.startswith(f"{base}-")


def _clean(name: str) -> str:
    for prefix in PREFIXES:
        if name.startswith(prefix):
            return name[len(prefix) :]
    return name


def _species(details: str) -> str:
    return details.split(", ")[0]


def _side_of(ref: str) -> str:
    return ref[:2]
