"""Pokémon Showdown's reference data: species, types, abilities, items, moves, and natures."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Any, LiteralString

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field

from api.db import Connection, paginate
from api.params import Limit, Offset, showdown_id
from api.responses import Envelope, ReferenceScope

router = APIRouter(prefix="/v1/reference", tags=["Reference data"])

NONSTANDARD = Field(description="e.g. Past or CAP for entries not in standard Gen 9 play; null for standard entries.")


class Species(BaseModel):
    species: str = Field(description="Showdown ID, e.g. ninetalesalola.")
    species_name: str
    dex_number: int
    base_species: str | None = Field(description="The base species, for alternate forms.")
    forme: str | None = Field(description="e.g. Alola for Ninetales-Alola.")
    type_1: str
    type_2: str | None = Field(description="Null for single-type species.")
    hp: int
    atk: int
    def_: int = Field(alias="def", serialization_alias="def")
    spa: int
    spd: int
    spe: int
    nonstandard: str | None = NONSTANDARD


class Type(BaseModel):
    type: str = Field(description="Showdown ID, e.g. water.")
    type_name: str


class Ability(BaseModel):
    ability: str = Field(description="Showdown ID, e.g. intimidate.")
    ability_name: str
    short_description: str | None
    nonstandard: str | None = NONSTANDARD


class Item(BaseModel):
    item: str = Field(description="Showdown ID, e.g. heavydutyboots.")
    item_name: str
    is_berry: bool
    short_description: str | None
    nonstandard: str | None = NONSTANDARD


class Move(BaseModel):
    move: str = Field(description="Showdown ID, e.g. earthquake.")
    move_name: str
    type: str
    category: str = Field(description="Physical, Special, or Status.")
    base_power: int
    accuracy: int | None = Field(description="Null if the move can't miss.")
    pp: int
    priority: int
    target: str = Field(description="e.g. normal or allAdjacentFoes.")
    short_description: str | None
    nonstandard: str | None = NONSTANDARD


class Nature(BaseModel):
    nature: str = Field(description="Showdown ID, e.g. timid.")
    nature_name: str
    increased_stat: str | None = Field(description="Null for neutral natures.")
    decreased_stat: str | None = Field(description="Null for neutral natures.")


class Kind(StrEnum):
    species = "species"
    types = "types"
    abilities = "abilities"
    items = "items"
    moves = "moves"
    natures = "natures"


@dataclass(frozen=True)
class KindQuery:
    view: LiteralString
    id_column: LiteralString
    columns: LiteralString
    model: type[BaseModel]


KINDS = {
    Kind.species: KindQuery(
        "species",
        "species",
        "species, species_name, dex_number, base_species, forme, type_1, type_2, hp, atk, def, spa, spd, spe, "
        "nonstandard",
        Species,
    ),
    Kind.types: KindQuery("type", "type", "type, type_name", Type),
    Kind.abilities: KindQuery("ability", "ability", "ability, ability_name, short_description, nonstandard", Ability),
    Kind.items: KindQuery("item", "item", "item, item_name, is_berry, short_description, nonstandard", Item),
    Kind.moves: KindQuery(
        "move",
        "move",
        "move, move_name, type, category, base_power, accuracy, pp, priority, target, short_description, nonstandard",
        Move,
    ),
    Kind.natures: KindQuery("nature", "nature", "nature, nature_name, increased_stat, decreased_stat", Nature),
}

type ReferenceRows = list[Species] | list[Type] | list[Ability] | list[Item] | list[Move] | list[Nature]
type ReferenceRow = Species | Type | Ability | Item | Move | Nature


@router.get("/{kind}")
def entries(conn: Connection, kind: Kind, limit: Limit = 50, offset: Offset = 0) -> Envelope[ReferenceRows]:
    """Every entry of one kind, by Showdown ID."""
    query = KINDS[kind]
    rows, page = paginate(conn, query.columns, f"api.{query.view}", "TRUE", query.id_column, (), limit, offset)
    return Envelope(scope=ReferenceScope(), sources=[], data=[build(query, row) for row in rows], page=page)


@router.get("/{kind}/{name}")
def entry(
    conn: Connection,
    kind: Kind,
    name: Annotated[str, Path(description="The entry's Showdown ID or name, e.g. heavydutyboots or Heavy-Duty Boots.")],
) -> Envelope[ReferenceRow]:
    """One entry, by Showdown ID or name."""
    query = KINDS[kind]
    entry_id = showdown_id(name, query.view)
    row = conn.execute(
        f"SELECT {query.columns} FROM api.{query.view} WHERE {query.id_column} = %s", (entry_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"No {kind.value} entry {entry_id!r}")
    return Envelope(scope=ReferenceScope(), sources=[], data=build(query, row))


def build(query: KindQuery, row: dict[str, Any]) -> Any:
    return query.model.model_validate(row)
