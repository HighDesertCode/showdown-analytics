"""Smogon's monthly usage statistics: ladder-wide, weighted by rating baseline, and scoped by team type."""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Any, LiteralString

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field

from api.db import Connection
from api.params import (
    DEFAULT_BASELINE,
    DEFAULT_FORMAT,
    Baseline,
    Format,
    Limit,
    Month,
    Offset,
    TeamType,
    format_month,
    parse_month,
    team_type_id,
    to_id,
)
from api.responses import Envelope, Page, SmogonScope, SourceFile

router = APIRouter(prefix="/v1/smogon", tags=["Smogon statistics"])

# How many rows of each section the Pokémon profile includes; the section endpoint returns them all.
PROFILE_SECTION_ROWS = 10

Species = Annotated[str, Path(description="The species' Showdown ID or name, e.g. ninetalesalola or Ninetales-Alola.")]


class AvailableMonth(BaseModel):
    month: str = Field(description="The reporting month, as YYYY-MM.")
    baseline: int = Field(description="The rating baseline teams are weighted by.")
    file_count: int = Field(description="The Smogon files behind this month and baseline.")
    last_retrieved_at: datetime = Field(description="When the newest of those files was downloaded.")


class PokemonUsage(BaseModel):
    rank: int = Field(description="The Pokémon's usage rank in this scope, 1 for the most used.")
    species: str = Field(description="The species' Showdown ID, e.g. ninetalesalola.")
    species_name: str = Field(description="The species' display name, e.g. Ninetales-Alola.")
    usage_share: float = Field(
        description=(
            "Share of teams in this scope with this Pokémon, from 0 to 1, weighted by the baseline. 0 when only "
            "players with no weight at this baseline used it."
        )
    )
    raw_count: int = Field(description="Teams in this scope with this Pokémon, unweighted.")
    raw_share: float = Field(description="Share of teams in this scope with this Pokémon, from 0 to 1, unweighted.")
    real_count: int = Field(description="Times this Pokémon was brought into battle.")
    real_share: float = Field(
        description="Share of all Pokémon brought into battle in this scope, from 0 to 1 (Smogon's Real % ÷ 600)."
    )
    battle_appearance_rate: float | None = Field(
        description=(
            "real_count ÷ raw_count: how often a team with this Pokémon brought it into battle, from 0 to 1, "
            "unweighted."
        )
    )
    viability_user_count: int | None = Field(
        description="Players using this Pokémon in Smogon's viability ceiling; null when Smogon omits it."
    )
    viability_top_gxe: int | None = Field(description="Highest GXE among those players.")
    viability_gxe_p99: int | None = Field(description="99th percentile GXE among those players.")
    viability_gxe_p95: int | None = Field(description="95th percentile GXE among those players.")


class AbilityShare(BaseModel):
    ability: str = Field(description="The ability's Showdown ID.")
    ability_name: str
    share: float = Field(description="Share of this Pokémon's sets with this ability; sums to 1 per Pokémon.")


class ItemShare(BaseModel):
    has_item: bool = Field(description="False for sets holding no item.")
    item: str | None = Field(description="The item's Showdown ID; null for sets holding no item.")
    item_name: str | None
    share: float = Field(description="Share of this Pokémon's sets holding this item; sums to 1 per Pokémon.")


class MoveShare(BaseModel):
    move: str = Field(description="The move's Showdown ID.")
    move_name: str
    share: float = Field(
        description="Share of this Pokémon's sets with this move; sums to at most 4 per Pokémon (four move slots)."
    )


class SpreadShare(BaseModel):
    spread: str = Field(description="Smogon's label, e.g. Timid:0/0/4/252/0/252.")
    nature: str = Field(description="The nature's Showdown ID.")
    nature_name: str
    hp_evs: int
    atk_evs: int
    def_evs: int
    spa_evs: int
    spd_evs: int
    spe_evs: int
    share: float = Field(description="Share of this Pokémon's sets with this nature and spread; sums to 1 per Pokémon.")


class TeammateShare(BaseModel):
    species: str = Field(description="The teammate's Showdown ID.")
    species_name: str
    share: float = Field(
        description=(
            "Share of this Pokémon's teams that include this teammate; sums to just under 5 per Pokémon, since "
            "Smogon omits negligible teammates."
        )
    )


class Counter(BaseModel):
    species: str = Field(description="The opponent's Showdown ID.")
    species_name: str
    encounters: float = Field(
        description="Weighted encounters between the two Pokémon that ended with one of them KOed or switched out."
    )
    ko_or_switch_rate: float = Field(
        description="Share of those encounters where this Pokémon was KOed or forced out by the opponent, 0 to 1."
    )
    ko_or_switch_rate_std_dev: float = Field(description="Standard deviation of ko_or_switch_rate.")
    score: float = Field(
        description="Smogon's ranking score: ko_or_switch_rate minus 4 standard deviations, a cautious estimate."
    )


class Lead(BaseModel):
    rank: int = Field(description="The Pokémon's lead rank in this scope, 1 for the most common lead.")
    lead_share: float = Field(description="Share of leads, weighted by the baseline; sums to 1 per scope.")
    raw_count: int = Field(description="Times this Pokémon led, unweighted.")
    raw_lead_share: float = Field(description="Share of leads, unweighted; sums to 1 per scope.")


class PokemonProfile(BaseModel):
    usage: PokemonUsage
    lead: Lead | None = Field(description="How often this Pokémon leads; null when it never led in this scope.")
    abilities: list[AbilityShare] = Field(description="The most common abilities, up to 10.")
    items: list[ItemShare] = Field(description="The most common items, up to 10.")
    moves: list[MoveShare] = Field(description="The most common moves, up to 10.")
    spreads: list[SpreadShare] = Field(description="The most common natures and EV spreads, up to 10.")
    teammates: list[TeammateShare] = Field(description="The most common teammates, up to 10.")
    counters: list[Counter] = Field(
        description="Checks and counters by Smogon's score, up to 10. Smogon publishes them for all teams only."
    )


type SectionRows = (
    list[AbilityShare] | list[ItemShare] | list[MoveShare] | list[SpreadShare] | list[TeammateShare] | list[Counter]
)


class Section(StrEnum):
    abilities = "abilities"
    items = "items"
    moves = "moves"
    spreads = "spreads"
    teammates = "teammates"
    counters = "counters"


@dataclass(frozen=True)
class SectionQuery:
    table: LiteralString
    columns: LiteralString
    order: LiteralString
    model: type[BaseModel]


SECTIONS = {
    Section.abilities: SectionQuery(
        "pokemon_ability", "ability, ability_name, share", "share DESC, ability", AbilityShare
    ),
    Section.items: SectionQuery(
        "pokemon_item", "has_item, item, item_name, share", "share DESC, item NULLS FIRST", ItemShare
    ),
    Section.moves: SectionQuery("pokemon_move", "move, move_name, share", "share DESC, move", MoveShare),
    Section.spreads: SectionQuery(
        "pokemon_spread",
        "spread, nature, nature_name, hp_evs, atk_evs, def_evs, spa_evs, spd_evs, spe_evs, share",
        "share DESC, spread",
        SpreadShare,
    ),
    Section.teammates: SectionQuery(
        "pokemon_teammate",
        "teammate_species AS species, teammate_species_name AS species_name, share",
        "share DESC, teammate_species",
        TeammateShare,
    ),
    Section.counters: SectionQuery(
        "pokemon_counter",
        "opponent_species AS species, opponent_species_name AS species_name, encounters, ko_or_switch_rate, "
        "ko_or_switch_rate_std_dev, score",
        "score DESC, opponent_species",
        Counter,
    ),
}


@router.get("/months")
def months(conn: Connection, format: Format = DEFAULT_FORMAT) -> Envelope[list[AvailableMonth]]:
    """The months and baselines with Smogon statistics, newest first. Every month listed is complete."""
    rows = conn.execute(
        """
        SELECT report_month, baseline, file_count, last_retrieved_at
        FROM api.available_month
        WHERE format = %s
        ORDER BY report_month DESC, baseline
        """,
        (format,),
    ).fetchall()
    data = [AvailableMonth(month=format_month(row.pop("report_month")), **row) for row in rows]
    return Envelope(scope=SmogonScope(format=format), sources=[], data=data)


@router.get("/usage")
def usage(
    conn: Connection,
    format: Format = DEFAULT_FORMAT,
    month: Month = None,
    baseline: Baseline = DEFAULT_BASELINE,
    team_type: TeamType = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> Envelope[list[PokemonUsage]]:
    """Pokémon ranked by usage in one scope: a month, baseline, and either all teams or teams of one type."""
    scope = resolve_scope(conn, format, month, baseline, team_type)
    total = count(conn, "pokemon_usage", scope)
    rows = conn.execute(
        f"""
        SELECT {USAGE_COLUMNS}
        FROM api.pokemon_usage
        WHERE {SCOPE_FILTER}
        ORDER BY rank, species
        LIMIT %s OFFSET %s
        """,
        (*scope.args, limit, offset),
    ).fetchall()
    return Envelope(
        scope=scope.echo,
        sources=source_files(conn, [scope.report["usage_source_file_id"], scope.report["chaos_source_file_id"]]),
        data=[PokemonUsage(**row) for row in rows],
        page=Page(limit=limit, offset=offset, total=total),
    )


@router.get("/pokemon/{species}")
def pokemon(
    conn: Connection,
    species: Species,
    format: Format = DEFAULT_FORMAT,
    month: Month = None,
    baseline: Baseline = DEFAULT_BASELINE,
    team_type: TeamType = None,
) -> Envelope[PokemonProfile]:
    """One Pokémon in one scope: its usage, how often it leads, and its most common abilities, items, moves,
    spreads, teammates, and checks and counters. Each list's full version is at /pokemon/{species}/{section}."""
    scope = resolve_scope(conn, format, month, baseline, team_type)
    species_id = to_id(species)
    row = conn.execute(
        f"SELECT {USAGE_COLUMNS} FROM api.pokemon_usage WHERE {SCOPE_FILTER} AND species = %s",
        (*scope.args, species_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"No Smogon usage for {species_id} {scope.describe()}")
    lead = conn.execute(
        f"""
        SELECT rank, lead_share, raw_count, raw_lead_share
        FROM api.pokemon_lead
        WHERE {SCOPE_FILTER} AND species = %s
        """,
        (*scope.args, species_id),
    ).fetchone()
    sections = {
        section.value: section_rows(conn, section, scope, species_id, PROFILE_SECTION_ROWS, 0) for section in Section
    }
    report = scope.report
    return Envelope(
        scope=scope.echo,
        sources=source_files(
            conn, [report["usage_source_file_id"], report["chaos_source_file_id"], report["leads_source_file_id"]]
        ),
        data=PokemonProfile(usage=PokemonUsage(**row), lead=Lead(**lead) if lead else None, **sections),
    )


@router.get("/pokemon/{species}/{section}")
def pokemon_section(
    conn: Connection,
    species: Species,
    section: Section,
    format: Format = DEFAULT_FORMAT,
    month: Month = None,
    baseline: Baseline = DEFAULT_BASELINE,
    team_type: TeamType = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> Envelope[SectionRows]:
    """Every ability, item, move, spread, teammate, or check and counter Smogon lists for one Pokémon in one scope,
    most common first (counters by Smogon's score)."""
    scope = resolve_scope(conn, format, month, baseline, team_type)
    species_id = to_id(species)
    exists = conn.execute(
        f"SELECT 1 FROM api.pokemon_usage WHERE {SCOPE_FILTER} AND species = %s", (*scope.args, species_id)
    ).fetchone()
    if exists is None:
        raise HTTPException(status_code=404, detail=f"No Smogon usage for {species_id} {scope.describe()}")
    query = SECTIONS[section]
    total = count(conn, query.table, scope, species_id)
    return Envelope(
        scope=scope.echo,
        sources=source_files(conn, [scope.report["chaos_source_file_id"]]),
        data=section_rows(conn, section, scope, species_id, limit, offset),
        page=Page(limit=limit, offset=offset, total=total),
    )


# Matches one scope's rows; overall reports have a null team type.
SCOPE_FILTER = "format = %s AND report_month = %s AND baseline = %s AND team_type IS NOT DISTINCT FROM %s"
USAGE_COLUMNS = (
    "rank, species, species_name, usage_share, raw_count, raw_share, real_count, real_share, battle_appearance_rate, "
    "viability_user_count, viability_top_gxe, viability_gxe_p99, viability_gxe_p95"
)


@dataclass(frozen=True)
class Scope:
    """A resolved scope: the filters with their defaults filled in, and its report row with the source file IDs."""

    format: str
    month: date
    baseline: int
    team_type: str | None
    report: dict[str, Any]

    @property
    def args(self) -> tuple[str, date, int, str | None]:
        """The values for SCOPE_FILTER's placeholders."""
        return (self.format, self.month, self.baseline, self.team_type)

    @property
    def echo(self) -> SmogonScope:
        return SmogonScope(
            format=self.format, month=format_month(self.month), baseline=self.baseline, team_type=self.team_type
        )

    def describe(self) -> str:
        teams = f"{self.team_type} teams" if self.team_type else "all teams"
        return f"for {self.format} in {format_month(self.month)} at baseline {self.baseline} ({teams})"


def resolve_scope(conn: Connection, format: str, month: str | None, baseline: int, team_type: str | None) -> Scope:
    """Fills in the default month and reads the scope's report row; a 404 when Smogon published no report for it."""
    report_month = resolve_month(conn, format, month, baseline)
    type_id = team_type_id(team_type)
    report = conn.execute(
        f"""
        SELECT usage_source_file_id, chaos_source_file_id, leads_source_file_id, metagame_source_file_id
        FROM api.report
        WHERE {SCOPE_FILTER}
        """,
        (format, report_month, baseline, type_id),
    ).fetchone()
    scope = Scope(format, report_month, baseline, type_id, report or {})
    if report is None:
        raise HTTPException(status_code=404, detail=f"No Smogon report {scope.describe()}")
    return scope


def resolve_month(conn: Connection, format: str, month: str | None, baseline: int) -> date:
    """The requested month, or the latest one with statistics at this baseline."""
    if month is not None:
        return parse_month(month)
    row = conn.execute(
        "SELECT MAX(report_month) AS latest FROM api.available_month WHERE format = %s AND baseline = %s",
        (format, baseline),
    ).fetchone()
    if row is None or row["latest"] is None:
        raise HTTPException(status_code=404, detail=f"No Smogon statistics for {format} at baseline {baseline}")
    return row["latest"]


def count(conn: Connection, table: LiteralString, scope: Scope, species: str | None = None) -> int:
    """Rows in one scope of an api table, for one Pokémon if given."""
    species_filter: LiteralString = " AND species = %s" if species is not None else ""
    args = (*scope.args, species) if species is not None else scope.args
    row = conn.execute(
        f"SELECT COUNT(*) AS total FROM api.{table} WHERE {SCOPE_FILTER}{species_filter}", args
    ).fetchone()
    return row["total"] if row else 0


def section_rows(conn: Connection, section: Section, scope: Scope, species: str, limit: int, offset: int) -> list[Any]:
    query = SECTIONS[section]
    rows = conn.execute(
        f"""
        SELECT {query.columns}
        FROM api.{query.table}
        WHERE {SCOPE_FILTER} AND species = %s
        ORDER BY {query.order}
        LIMIT %s OFFSET %s
        """,
        (*scope.args, species, limit, offset),
    ).fetchall()
    return [query.model(**row) for row in rows]


def source_files(conn: Connection, ids: list[int | None]) -> list[SourceFile]:
    rows = conn.execute(
        """
        SELECT source_file_id, family, url, retrieved_at
        FROM api.source_file
        WHERE source_file_id = ANY(%s)
        ORDER BY family
        """,
        ([source_file_id for source_file_id in ids if source_file_id is not None],),
    ).fetchall()
    return [SourceFile(**row) for row in rows]
