-- One row per weighted option for a Pokémon, with Smogon's label as published
-- (e.g. "leftovers", "Timid:4/0/0/252/0/252", "Pecharunt"). Weights can be 0.
CREATE TABLE raw.chaos_option (
    chaos_pokemon_id bigint           NOT NULL REFERENCES raw.chaos_pokemon (chaos_pokemon_id),
    category         text             NOT NULL CHECK (category IN ('abilities', 'items', 'moves', 'spreads', 'teammates', 'tera_types', 'happiness')),
    label            text             NOT NULL,
    weight           double precision NOT NULL CHECK (weight >= 0),
    PRIMARY KEY (chaos_pokemon_id, category, label)
);
