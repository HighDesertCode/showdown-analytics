-- One row per check or counter for a Pokémon. n, p, and d are Smogon's keys as published;
-- staging gives them descriptive names. Only overall (not per-type) reports include counters.
CREATE TABLE raw.chaos_counter (
    chaos_pokemon_id bigint           NOT NULL REFERENCES raw.chaos_pokemon (chaos_pokemon_id),
    opponent         text             NOT NULL,
    n                double precision NOT NULL CHECK (n >= 0),
    p                double precision NOT NULL CHECK (p BETWEEN 0 AND 1),
    d                double precision NOT NULL CHECK (d >= 0),
    PRIMARY KEY (chaos_pokemon_id, opponent)
);
