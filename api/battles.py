"""Individual public Pokémon Showdown replays: search them, and follow one turn by turn."""

from datetime import datetime
from typing import Annotated, Any, LiteralString

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field

from api.db import Connection
from api.params import (
    DEFAULT_FORMAT,
    EloBand,
    Format,
    Limit,
    Month,
    Offset,
    TeamType,
    format_month,
    optional_id,
    parse_month,
    type_id,
)
from api.responses import BattleScope, Envelope, Page

router = APIRouter(prefix="/v1/battles", tags=["Battles"])

ReplayId = Annotated[str, Path(description="Showdown's replay ID, e.g. gen9monotype-2691037303.")]


class Side(BaseModel):
    side: str = Field(description="p1 or p2.")
    player: str = Field(description="The player's name as the log shows it.")
    player_id: str = Field(description="Showdown's user ID for the player.")
    elo_before: int | None = Field(
        description="The player's Showdown Elo before the battle; null if unrated. Not comparable to Smogon's "
        "baselines."
    )
    elo_after: int | None = Field(description="The player's Elo after the battle; null if unrated or not shown.")
    elo_band: int | None = Field(description="The lower bound of elo_before: 1000, 1200, 1400, or 1600 and up.")
    result: str = Field(description="win, loss, or tie.")
    team_type: str | None = Field(
        description="Inferred, not read from the log: the one type all six previewed Pokémon share. Null when they "
        "share none or more than one."
    )


class BattleBase(BaseModel):
    replay_id: str = Field(description="Showdown's replay ID.")
    replay_url: str = Field(description="The replay's public page on Showdown, where the battle can be watched.")
    rated: bool = Field(
        description="Whether the battle counted for the ladder; challenges and tournaments are unrated."
    )
    started_at: datetime
    ended_at: datetime
    turns: int
    winner: str | None = Field(description="The winning side, p1 or p2; null for a tie.")
    ended_by: str = Field(description="knockout, forfeit, inactivity, or tie.")


class Battle(BattleBase):
    sides: list[Side] = Field(description="Both players, p1 first.")


class PreviewedPokemon(BaseModel):
    slot: int = Field(description="Its position in team preview, 1 to 6.")
    previewed_species: str = Field(description='The species as previewed; "Urshifu-*" hides which form it is.')
    species: str = Field(description="The matched species' Showdown ID; the base species for a hidden form.")
    species_name: str
    form_hidden: bool = Field(description="True when team preview hid the form, as with Urshifu-*.")
    nickname: str | None = Field(description="Null if it never switched in.")


class SideWithTeam(Side):
    team: list[PreviewedPokemon] = Field(description="The six Pokémon shown at team preview, in preview order.")


class BattleDetail(BattleBase):
    rules: list[str] = Field(
        description="The battle's rules, e.g. Same Type Clause; unrated challenges can change them."
    )
    uploaded_at: datetime = Field(description="When the replay was uploaded.")
    sides: list[SideWithTeam] = Field(description="Both players and their previewed teams, p1 first.")


class Event(BaseModel):
    seq: int = Field(description="The event's position in the battle, from 1.")
    turn: int = Field(description="0 for events before the first turn, such as the leads switching in.")
    side: str | None = Field(description="The side of the Pokémon acting or affected; null for field events.")
    pokemon: str | None = Field(description="The Pokémon as shown at team preview, e.g. Urshifu-*.")
    species: str | None = Field(description="The form it is in at this event, e.g. urshifurapidstrike.")
    species_name: str | None
    event: str = Field(description="What happened, e.g. move, damage, switch, or side start.")
    detail: str | None = Field(description="The move, ability, condition, or species involved.")
    target_side: str | None
    target_pokemon: str | None
    target_species: str | None = Field(description="The form the target is in at this event.")
    target_species_name: str | None
    damage_percent: int | None = Field(
        description="HP lost, as a percent of max HP; capped at the HP the target had left."
    )
    hp_after_percent: int | None = Field(description="HP left afterwards, as a percent of max HP.")
    healed_percent: int | None = Field(description="HP restored, as a percent of max HP.")
    caused_by_seq: int | None = Field(
        description="The seq of the event that caused this one, such as the move behind a hit."
    )
    source: str | None = Field(description="The cause the log names, e.g. Stealth Rock or item Life Orb.")
    source_inferred: bool = Field(description="True when the cause was deduced rather than read from the log.")


SIDE_COLUMNS: LiteralString = "side, player, player_id, elo_before, elo_after, elo_band, result, team_type"
BATTLE_COLUMNS: LiteralString = "replay_id, replay_url, rated, started_at, ended_at, turns, winner, ended_by"


@router.get("")
def search(
    conn: Connection,
    format: Format = DEFAULT_FORMAT,
    month: Month = None,
    rated: Annotated[bool | None, Query(description="Only rated (true) or unrated (false) battles.")] = None,
    team_type: TeamType = None,
    elo_band: EloBand = None,
    player: Annotated[str | None, Query(description="Only battles this player played, by name or user ID.")] = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> Envelope[list[Battle]]:
    """Public replays, newest first. Team type, Elo band, and player all apply to the same side, so
    player=X&team_type=water finds the battles X played with a Water team."""
    type_filter = type_id(team_type)
    player_id = optional_id(player, "player name")
    band = int(elo_band) if elo_band is not None else None

    conditions: list[LiteralString] = ["battle.format = %s"]
    args: list[Any] = [format]
    if month is not None:
        conditions.append("battle.report_month = %s")
        args.append(parse_month(month))
    if rated is not None:
        conditions.append("battle.rated = %s")
        args.append(rated)
    side_conditions: list[LiteralString] = []
    for condition, value in (
        ("side.team_type = %s", type_filter),
        ("side.elo_band = %s", band),
        ("side.player_id = %s", player_id),
    ):
        if value is not None:
            side_conditions.append(condition)
            args.append(value)
    if side_conditions:
        conditions.append(
            "EXISTS (SELECT 1 FROM api.replay_battle_side AS side WHERE side.replay_id = battle.replay_id AND "
            + " AND ".join(side_conditions)
            + ")"
        )
    where = " AND ".join(conditions)

    total = conn.execute(f"SELECT COUNT(*) AS total FROM api.replay_battle AS battle WHERE {where}", args).fetchone()
    battles = conn.execute(
        f"""
        SELECT {BATTLE_COLUMNS}
        FROM api.replay_battle AS battle
        WHERE {where}
        ORDER BY battle.started_at DESC, battle.replay_id
        LIMIT %s OFFSET %s
        """,
        (*args, limit, offset),
    ).fetchall()
    sides = sides_by_replay(conn, [battle["replay_id"] for battle in battles])
    return Envelope(
        scope=BattleScope(
            format=format, month=month, rated=rated, team_type=type_filter, elo_band=band, player=player_id
        ),
        sources=[],
        data=[Battle(**battle, sides=sides.get(battle["replay_id"], [])) for battle in battles],
        page=Page(limit=limit, offset=offset, total=total["total"] if total else 0),
    )


@router.get("/{replay_id}")
def battle(conn: Connection, replay_id: ReplayId) -> Envelope[BattleDetail]:
    """One battle: its result, rules, and both players with the teams they showed at team preview."""
    row = find_battle(conn, replay_id, f"{BATTLE_COLUMNS}, rules, uploaded_at, format, report_month")
    teams: dict[str, list[PreviewedPokemon]] = {}
    for pokemon in conn.execute(
        """
        SELECT pokemon.side, pokemon.slot, pokemon.previewed_species, species.species, species.species_name,
            pokemon.form_hidden, pokemon.nickname
        FROM api.replay_battle_pokemon AS pokemon
        INNER JOIN api.species AS species ON species.species_id = pokemon.species_id
        WHERE pokemon.replay_id = %s
        ORDER BY pokemon.side, pokemon.slot
        """,
        (replay_id,),
    ).fetchall():
        teams.setdefault(pokemon.pop("side"), []).append(PreviewedPokemon(**pokemon))
    sides = [
        SideWithTeam(**side.model_dump(), team=teams.get(side.side, []))
        for side in sides_by_replay(conn, [replay_id]).get(replay_id, [])
    ]
    scope = BattleScope(format=row.pop("format"), month=format_month(row.pop("report_month")))
    return Envelope(scope=scope, sources=[], data=BattleDetail(**row, sides=sides))


@router.get("/{replay_id}/events")
def events(
    conn: Connection,
    replay_id: ReplayId,
    turn: Annotated[int | None, Query(ge=0, description="Only this turn's events; 0 is before the first turn.")] = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> Envelope[list[Event]]:
    """Every game event in a battle in order: moves, switches, damage and healing, status, boosts, hazards, and
    revealed abilities and items. Causes the parser deduced are flagged with source_inferred."""
    row = find_battle(conn, replay_id, "format, report_month")
    conditions: list[LiteralString] = ["event.replay_id = %s"]
    args: list[Any] = [replay_id]
    if turn is not None:
        conditions.append("event.turn = %s")
        args.append(turn)
    where = " AND ".join(conditions)
    total = conn.execute(
        f"SELECT COUNT(*) AS total FROM api.replay_battle_event AS event WHERE {where}", args
    ).fetchone()
    rows = conn.execute(
        f"""
        SELECT event.seq, event.turn, event.side, event.pokemon, species.species, species.species_name, event.event,
            event.detail, event.target_side, event.target_pokemon, target.species AS target_species,
            target.species_name AS target_species_name, event.damage_percent, event.hp_after_percent,
            event.healed_percent, event.caused_by_seq, event.source, event.source_inferred
        FROM api.replay_battle_event AS event
        LEFT JOIN api.species AS species ON species.species_id = event.species_id
        LEFT JOIN api.species AS target ON target.species_id = event.target_species_id
        WHERE {where}
        ORDER BY event.seq
        LIMIT %s OFFSET %s
        """,
        (*args, limit, offset),
    ).fetchall()
    return Envelope(
        scope=BattleScope(format=row["format"], month=format_month(row["report_month"])),
        sources=[],
        data=[Event(**event) for event in rows],
        page=Page(limit=limit, offset=offset, total=total["total"] if total else 0),
    )


def find_battle(conn: Connection, replay_id: str, columns: LiteralString) -> dict[str, Any]:
    row = conn.execute(f"SELECT {columns} FROM api.replay_battle WHERE replay_id = %s", (replay_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"No parsed replay {replay_id}")
    return row


def sides_by_replay(conn: Connection, replay_ids: list[str]) -> dict[str, list[Side]]:
    sides: dict[str, list[Side]] = {}
    for side in conn.execute(
        f"""
        SELECT replay_id, {SIDE_COLUMNS}
        FROM api.replay_battle_side
        WHERE replay_id = ANY(%s)
        ORDER BY replay_id, side
        """,
        (replay_ids,),
    ).fetchall():
        sides.setdefault(side.pop("replay_id"), []).append(Side(**side))
    return sides
