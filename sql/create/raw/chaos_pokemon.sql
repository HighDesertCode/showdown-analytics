-- One row per Pokémon in a chaos report, with Smogon's display name as published (e.g. "Iron Valiant").
-- viability_* are the four "Viability Ceiling" values: user count, top GXE, and 99th and 95th percentile GXE.
CREATE TABLE raw.chaos_pokemon (
    chaos_pokemon_id     bigint           GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_file_id       bigint           NOT NULL REFERENCES raw.chaos_report (source_file_id),
    pokemon              text             NOT NULL,
    raw_count            integer          NOT NULL CHECK (raw_count >= 0),
    usage                double precision NOT NULL CHECK (usage BETWEEN 0 AND 1),
    viability_user_count integer          NOT NULL,
    viability_top_gxe    integer          NOT NULL,
    viability_gxe_p99    integer          NOT NULL,
    viability_gxe_p95    integer          NOT NULL,
    CONSTRAINT chaos_pokemon_unique UNIQUE (source_file_id, pokemon)
);
