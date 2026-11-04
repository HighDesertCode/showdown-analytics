"""Statistics from public Pokémon Showdown replays: a sample of uploaded battles, by month and Elo band.

They count rated battles only, and are kept apart from Smogon's ladder-wide statistics.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Annotated, Any, LiteralString

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from api.db import Connection, paginate
from api.params import (
    DEFAULT_FORMAT,
    EloBand,
    Format,
    Limit,
    Month,
    Offset,
    TeamType,
    Type,
    format_month,
    optional_id,
    parse_month,
    type_id,
)
from api.responses import NOT_FOUND, Envelope, Page, ReplayScope

router = APIRouter(prefix="/v1/replays", tags=["Replay statistics"])


class BandSample(BaseModel):
    elo_band: int = Field(description="The players' Elo band.")
    team_count: int = Field(description="Teams in rated battles whose player was in this band.")
    typed_team_count: int = Field(
        description="Those teams with an inferred type (all six previewed Pokémon share exactly one type), the ones "
        "the type-based statistics count."
    )


class ReplayTypeMatchup(BaseModel):
    elo_band: int = Field(description="The team's Elo band; the opponent can be in another.")
    type: str = Field(description="The team's inferred type, as a Showdown ID.")
    type_name: str = Field(description="The team type's display name, e.g. Water.")
    opponent_type: str = Field(description="The opposing team's inferred type.")
    opponent_type_name: str = Field(description="The opposing team type's display name.")
    is_mirror: bool = Field(description="True when a type faces itself.")
    battle_count: int = Field(description="Rated battles between the two types.")
    win_count: int = Field(description="Those battles this type won.")
    tie_count: int = Field(description="Those battles that ended in a tie.")
    win_rate: float | None = Field(
        description="win_count ÷ battle_count, from 0 to 1, so ties count against it; null for mirror matches."
    )


class ReplayLead(BaseModel):
    elo_band: int = Field(description="The team's Elo band.")
    team_type: str = Field(description="The team's inferred type, as a Showdown ID.")
    species: str = Field(description="The lead's species, in the form it entered as, e.g. urshifurapidstrike.")
    species_name: str = Field(description="The species' display name, e.g. Urshifu-Rapid-Strike.")
    lead_count: int = Field(description="Teams of this type and band that led with this Pokémon.")
    team_count: int = Field(
        description="Teams of this type and band that sent out a lead, the denominator of lead_share. A battle "
        "forfeited at team preview has no lead."
    )
    lead_share: float = Field(description="lead_count ÷ team_count, from 0 to 1; sums to 1 per type and band.")
    win_count: int = Field(description="Battles the teams with this lead won.")
    win_rate: float = Field(description="win_count ÷ lead_count, from 0 to 1.")


class MoveDamage(BaseModel):
    elo_band: int = Field(description="The attacker's Elo band.")
    species: str = Field(description="The attacker, in the form it was in.")
    species_name: str = Field(description="The attacker's display name.")
    move: str = Field(description="The move's Showdown ID.")
    move_name: str = Field(description="The move's display name, e.g. Earthquake.")
    hit_count: int = Field(description="Hits that dealt damage; each hit of a multi-hit move counts.")
    mean_damage_percent: float = Field(
        description="Mean damage per hit, as a percent (0 to 100) of the target's max HP. A hit is capped at the HP "
        "its target had left, so a strong move's mean understates it."
    )
    knockout_count: int = Field(description="Hits that left the target with no HP.")


class HazardDamage(BaseModel):
    elo_band: int = Field(description="The Elo band of the team taking the damage.")
    team_type: str = Field(
        description="That team's inferred type, as a Showdown ID. Teams without an inferred type aren't counted."
    )
    hazard: str = Field(description="Stealth Rock or Spikes, as the log names it.")
    hit_count: int = Field(description="Times a Pokémon took damage from this hazard on switching in.")
    mean_damage_percent: float = Field(description="Mean damage per hit, as a percent (0 to 100) of max HP.")
    knockout_count: int = Field(description="Hits that left the Pokémon with no HP.")


@router.get("/sample", responses=NOT_FOUND)
def sample(
    conn: Connection, format: Format = DEFAULT_FORMAT, month: Month = None, elo_band: EloBand = None
) -> Envelope[ReplayScope, list[BandSample]]:
    """How many battles and teams the replay statistics rest on in a month, by Elo band. Check these before
    trusting a rate: a small band means a noisy one."""
    scope = resolve_scope(conn, format, month, elo_band)
    rows = conn.execute(
        f"""
        SELECT elo_band, team_count, typed_team_count
        FROM api.replay_sample
        WHERE {scope.filter}
        ORDER BY elo_band
        """,
        scope.args,
    ).fetchall()
    return Envelope(scope=scope.echo, sources=[], data=[BandSample(**row) for row in rows])


@router.get("/type-matchups", responses=NOT_FOUND)
def type_matchups(
    conn: Connection,
    format: Format = DEFAULT_FORMAT,
    month: Month = None,
    elo_band: EloBand = None,
    type: Type = None,
    opponent_type: Type = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> Envelope[ReplayScope, list[ReplayTypeMatchup]]:
    """Rated battles, wins, and win rate for each team type against each other type, by the team's Elo band."""
    team, opponent = type_id(type), type_id(opponent_type)
    scope = resolve_scope(conn, format, month, elo_band)
    rows, page = page_rows(
        conn,
        scope,
        "replay_type_matchup",
        "elo_band, type, type_name, opponent_type, opponent_type_name, is_mirror, battle_count, win_count, tie_count, "
        "win_rate",
        [("type = %s", team), ("opponent_type = %s", opponent)],
        "elo_band, type, opponent_type",
        limit,
        offset,
    )
    return Envelope(
        scope=scope.echo,
        sources=[],
        data=[ReplayTypeMatchup(**row) for row in rows],
        page=page,
    )


@router.get("/leads", responses=NOT_FOUND)
def leads(
    conn: Connection,
    format: Format = DEFAULT_FORMAT,
    month: Month = None,
    elo_band: EloBand = None,
    team_type: TeamType = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> Envelope[ReplayScope, list[ReplayLead]]:
    """How often each Pokémon leads a team of its type, and how often those teams win, by Elo band. Most common
    leads first within each type and band."""
    team = type_id(team_type)
    scope = resolve_scope(conn, format, month, elo_band)
    rows, page = page_rows(
        conn,
        scope,
        "replay_lead",
        "elo_band, team_type, species, species_name, lead_count, team_count, lead_share, win_count, win_rate",
        [("team_type = %s", team)],
        "elo_band, team_type, lead_share DESC, species",
        limit,
        offset,
    )
    return Envelope(
        scope=scope.echo,
        sources=[],
        data=[ReplayLead(**row) for row in rows],
        page=page,
    )


@router.get("/move-damage", responses=NOT_FOUND)
def move_damage(
    conn: Connection,
    format: Format = DEFAULT_FORMAT,
    month: Month = None,
    elo_band: EloBand = None,
    species: Annotated[str | None, Query(description="Only this attacker, e.g. swampert or Swampert.")] = None,
    move: Annotated[str | None, Query(description="Only this move, e.g. earthquake or Earthquake.")] = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> Envelope[ReplayScope, list[MoveDamage]]:
    """Direct hits from each Pokémon's moves on the opposing Pokémon, by the attacker's Elo band: hits, mean damage,
    and knockouts. Most hits first."""
    attacker, attack = optional_id(species, "species"), optional_id(move, "move")
    scope = resolve_scope(conn, format, month, elo_band)
    rows, page = page_rows(
        conn,
        scope,
        "replay_move_damage",
        "elo_band, species, species_name, move, move_name, hit_count, mean_damage_percent, knockout_count",
        [("species = %s", attacker), ("move = %s", attack)],
        "elo_band, hit_count DESC, species, move",
        limit,
        offset,
    )
    return Envelope(
        scope=scope.echo,
        sources=[],
        data=[MoveDamage(**row) for row in rows],
        page=page,
    )


@router.get("/hazard-damage", responses=NOT_FOUND)
def hazard_damage(
    conn: Connection,
    format: Format = DEFAULT_FORMAT,
    month: Month = None,
    elo_band: EloBand = None,
    team_type: TeamType = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> Envelope[ReplayScope, list[HazardDamage]]:
    """Damage from Stealth Rock and Spikes by the Elo band and inferred type of the team taking it."""
    team = type_id(team_type)
    scope = resolve_scope(conn, format, month, elo_band)
    rows, page = page_rows(
        conn,
        scope,
        "replay_hazard_damage",
        "elo_band, team_type, hazard, hit_count, mean_damage_percent, knockout_count",
        [("team_type = %s", team)],
        "elo_band, team_type, hazard",
        limit,
        offset,
    )
    return Envelope(
        scope=scope.echo,
        sources=[],
        data=[HazardDamage(**row) for row in rows],
        page=page,
    )


@dataclass(frozen=True)
class Scope:
    """A resolved replay scope: the filters with their defaults filled in, and the month's sample size."""

    format: str
    month: date
    elo_band: int | None
    battle_count: int
    rated_battle_count: int

    @property
    def filter(self) -> LiteralString:
        """A WHERE condition matching this scope's rows; its values are args."""
        if self.elo_band is None:
            return "format = %s AND report_month = %s"
        return "format = %s AND report_month = %s AND elo_band = %s"

    @property
    def args(self) -> tuple[Any, ...]:
        if self.elo_band is None:
            return (self.format, self.month)
        return (self.format, self.month, self.elo_band)

    @property
    def echo(self) -> ReplayScope:
        return ReplayScope(
            format=self.format,
            month=format_month(self.month),
            partial_month=self.month >= datetime.now(UTC).date().replace(day=1),
            elo_band=self.elo_band,
            battle_count=self.battle_count,
            rated_battle_count=self.rated_battle_count,
        )


def resolve_scope(conn: Connection, format: str, month: str | None, elo_band: int | None) -> Scope:
    """Fills in the default month (the latest with replays) and reads its sample size; a 404 when it has none."""
    if month is None:
        row = conn.execute(
            "SELECT MAX(report_month) AS latest FROM api.replay_sample WHERE format = %s", (format,)
        ).fetchone()
        if row is None or row["latest"] is None:
            raise HTTPException(status_code=404, detail=f"No replay statistics for {format}")
        replay_month = row["latest"]
    else:
        replay_month = parse_month(month)
    sample = conn.execute(
        """
        SELECT MIN(battle_count) AS battle_count, MIN(rated_battle_count) AS rated_battle_count
        FROM api.replay_sample
        WHERE format = %s AND report_month = %s
        """,
        (format, replay_month),
    ).fetchone()
    if sample is None or sample["battle_count"] is None:
        raise HTTPException(
            status_code=404, detail=f"No replay statistics for {format} in {format_month(replay_month)}"
        )
    band = int(elo_band) if elo_band is not None else None
    return Scope(format, replay_month, band, sample["battle_count"], sample["rated_battle_count"])


def page_rows(
    conn: Connection,
    scope: Scope,
    table: LiteralString,
    columns: LiteralString,
    filters: list[tuple[LiteralString, Any]],
    order: LiteralString,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], Page]:
    """One page of a replay table's rows in the scope, with the optional filters that have a value."""
    conditions: list[LiteralString] = [scope.filter]
    args: list[Any] = list(scope.args)
    for condition, value in filters:
        if value is not None:
            conditions.append(condition)
            args.append(value)
    return paginate(conn, columns, f"api.{table}", " AND ".join(conditions), order, args, limit, offset)
