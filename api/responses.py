"""The envelope every response shares: what the data covers, where it came from, and which page it is."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SmogonScope(BaseModel):
    """What a Smogon statistic covers. The API fills in defaults for any filter left out, and echoes them here."""

    source: Literal["smogon"] = Field(
        "smogon", description="Smogon's monthly usage statistics, which cover every rated ladder battle in the format."
    )
    format: str = Field(description="The Showdown format, e.g. gen9monotype.")
    month: str | None = Field(None, description="The reporting month, as YYYY-MM.")
    baseline: int | None = Field(
        None,
        description=(
            "The rating baseline teams are weighted by: 1630 or 1760. It weights each team by how likely its player's "
            "rating is above that number; it is not a rating cutoff."
        ),
    )
    team_type: str | None = Field(
        None, description="The team type's Showdown ID (e.g. water) for teams of that type only; null for all teams."
    )


class ReplayScope(BaseModel):
    """What a replay statistic covers. The API fills in defaults for any filter left out, and echoes them here."""

    source: Literal["replays"] = Field(
        "replays",
        description=(
            "Public Pokémon Showdown replays: a sample of the battles players chose to upload, not the whole ladder. "
            "Never comparable to Smogon's statistics."
        ),
    )
    format: str = Field(description="The Showdown format, e.g. gen9monotype.")
    month: str = Field(description="The UTC month the battles started in, as YYYY-MM.")
    partial_month: bool = Field(description="True while the month is still in progress, so its counts keep growing.")
    elo_band: int | None = Field(
        None,
        description=(
            "The Elo band of the player or team counted, by the lower bound of their Showdown Elo before the battle "
            "(1000, 1200, 1400, or 1600 and up); null for every band, each in its own rows. Elo isn't comparable to "
            "Smogon's baselines."
        ),
    )
    battle_count: int = Field(description="Battles in the sample that month, rated or not.")
    rated_battle_count: int = Field(
        description="Rated battles in the sample that month; the statistics count only these."
    )


class BattleScope(BaseModel):
    """Which individual battles a response covers, with the search filters it applied."""

    source: Literal["replay_battles"] = Field(
        "replay_battles",
        description=(
            "Individual public Pokémon Showdown replays, as their logs show them: a sample of the battles players "
            "chose to upload, not the whole ladder."
        ),
    )
    format: str = Field(description="The Showdown format, e.g. gen9monotype.")
    month: str | None = Field(None, description="Only battles that started in this UTC month, as YYYY-MM.")
    rated: bool | None = Field(None, description="Only rated (true) or unrated (false) battles.")
    team_type: str | None = Field(None, description="Only battles where a side's team had this inferred type.")
    elo_band: int | None = Field(None, description="Only battles where a side's player was in this Elo band.")
    player: str | None = Field(None, description="Only battles this player played, by Showdown user ID.")


class ReferenceScope(BaseModel):
    """Reference data, which has no reporting period or sample."""

    source: Literal["reference"] = Field(
        "reference",
        description=(
            "Pokémon Showdown's own data files: species, types, abilities, items, moves, and natures as Showdown "
            "currently defines them, including entries no longer legal (marked in nonstandard)."
        ),
    )


class SourceFile(BaseModel):
    """A Smogon file the data was loaded from."""

    source_file_id: int
    family: str = Field(description="The report family: chaos, usage, leads, metagame, or matchup_chart.")
    url: str = Field(description="Where the file is published on smogon.com.")
    retrieved_at: datetime = Field(description="When the file was downloaded.")


class Page(BaseModel):
    limit: int = Field(description="The most rows returned.")
    offset: int = Field(description="Rows skipped before the first one returned.")
    total: int = Field(description="Rows matching the request across every page.")


class Envelope[T](BaseModel):
    scope: SmogonScope | ReplayScope | BattleScope | ReferenceScope = Field(discriminator="source")
    sources: list[SourceFile] = Field(
        description="The Smogon files behind this data; empty for replay data, where each battle is its own source."
    )
    data: T
    page: Page | None = Field(None, description="Set when the data is paginated.")
