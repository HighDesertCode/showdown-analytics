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
    scope: SmogonScope
    sources: list[SourceFile] = Field(description="The files behind this data.")
    data: T
    page: Page | None = Field(None, description="Set when the data is paginated.")
