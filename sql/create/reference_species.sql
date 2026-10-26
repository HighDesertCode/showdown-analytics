-- One row per battle-relevant Pokémon species or form from Showdown's pokedex.json.
-- Cosmetic forms (e.g. Vivillon-Icy Snow) are excluded; they share their base form's types and stats.
CREATE TABLE reference.species (
    species_id   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    showdown_id  text     NOT NULL UNIQUE CHECK (showdown_id ~ '^[a-z0-9]+$'),
    name         text     NOT NULL,
    dex_number   smallint NOT NULL,
    base_species text,
    forme        text,
    type_1_id    bigint   NOT NULL REFERENCES reference.type (type_id),
    type_2_id    bigint   REFERENCES reference.type (type_id),
    hp           smallint NOT NULL CHECK (hp  BETWEEN 0 AND 255),
    atk          smallint NOT NULL CHECK (atk BETWEEN 0 AND 255),
    def          smallint NOT NULL CHECK (def BETWEEN 0 AND 255),
    spa          smallint NOT NULL CHECK (spa BETWEEN 0 AND 255),
    spd          smallint NOT NULL CHECK (spd BETWEEN 0 AND 255),
    spe          smallint NOT NULL CHECK (spe BETWEEN 0 AND 255),
    nonstandard  text,
    CONSTRAINT species_types_distinct CHECK (type_2_id <> type_1_id),
    CONSTRAINT species_forme_pairing  CHECK ((base_species IS NULL) = (forme IS NULL))
);
