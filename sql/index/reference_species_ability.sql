-- Supports lookups of species by ability (e.g. which Pokémon can have Levitate).
CREATE INDEX species_ability_ability_id_idx ON reference.species_ability (ability_id);
