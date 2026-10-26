-- Links each species to its abilities by slot: '0' and '1' (regular) and 'H' (hidden).
-- Special-event abilities (Showdown slot 'S') are excluded.
CREATE TABLE reference.species_ability (
    species_id bigint NOT NULL REFERENCES reference.species (species_id),
    slot       text   NOT NULL CHECK (slot IN ('0', '1', 'H')),
    ability_id bigint NOT NULL REFERENCES reference.ability (ability_id),
    PRIMARY KEY (species_id, slot),
    CONSTRAINT species_ability_unique UNIQUE (species_id, ability_id)
);
