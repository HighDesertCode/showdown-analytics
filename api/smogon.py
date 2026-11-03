"""Smogon's monthly usage statistics: ladder-wide, weighted by rating baseline, and scoped by team type."""

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
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
)
from api.responses import Envelope, Page, SmogonScope, SourceFile

router = APIRouter(prefix="/v1/smogon", tags=["Smogon statistics"])


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
    viability_user_count: int | None = Field(
        description="Players using this Pokémon in Smogon's viability ceiling; null when Smogon omits it."
    )
    viability_top_gxe: int | None = Field(description="Highest GXE among those players.")
    viability_gxe_p99: int | None = Field(description="99th percentile GXE among those players.")
    viability_gxe_p95: int | None = Field(description="95th percentile GXE among those players.")


@router.get("/months")
def months(conn: Connection, format: Format = DEFAULT_FORMAT) -> Envelope[AvailableMonth]:
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
) -> Envelope[PokemonUsage]:
    """Pokémon ranked by usage in one scope: a month, baseline, and either all teams or teams of one type."""
    report_month = resolve_month(conn, format, month, baseline)
    type_id = team_type_id(team_type)
    report = find_report(conn, format, report_month, baseline, type_id)
    scope_args = (format, report_month, baseline, type_id)
    total = conn.execute(f"SELECT COUNT(*) AS total FROM api.pokemon_usage WHERE {SCOPE_FILTER}", scope_args).fetchone()
    rows = conn.execute(
        f"""
        SELECT rank, species, species_name, usage_share, raw_count, raw_share, real_count, real_share,
            viability_user_count, viability_top_gxe, viability_gxe_p99, viability_gxe_p95
        FROM api.pokemon_usage
        WHERE {SCOPE_FILTER}
        ORDER BY rank, species
        LIMIT %s OFFSET %s
        """,
        (*scope_args, limit, offset),
    ).fetchall()
    return Envelope(
        scope=SmogonScope(format=format, month=format_month(report_month), baseline=baseline, team_type=type_id),
        sources=source_files(conn, [report["usage_source_file_id"], report["chaos_source_file_id"]]),
        data=[PokemonUsage(**row) for row in rows],
        page=Page(limit=limit, offset=offset, total=total["total"] if total else 0),
    )


# Matches one scope's rows; overall reports have a null team type.
SCOPE_FILTER = "format = %s AND report_month = %s AND baseline = %s AND team_type IS NOT DISTINCT FROM %s"


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


def find_report(conn: Connection, format: str, month: date, baseline: int, type_id: str | None) -> dict[str, Any]:
    """The scope's report row, with its source file IDs; a 404 when Smogon published no report for it."""
    report = conn.execute(
        f"""
        SELECT usage_source_file_id, chaos_source_file_id, leads_source_file_id, metagame_source_file_id
        FROM api.report
        WHERE {SCOPE_FILTER}
        """,
        (format, month, baseline, type_id),
    ).fetchone()
    if report is None:
        teams = f"{type_id} teams" if type_id else "all teams"
        raise HTTPException(
            status_code=404,
            detail=f"No Smogon report for {format} in {format_month(month)} at baseline {baseline} for {teams}",
        )
    return report


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
