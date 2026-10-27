-- One row per Pokémon in a usage report, with values as printed. Only usage_percent is weighted by the
-- baseline; raw (team appearances) and real (brought into battle) counts are the same at every baseline.
-- real_percent is scaled so a report's values sum to 600% (six slots), so it can exceed 100%.
CREATE TABLE raw.usage_pokemon (
    source_file_id bigint  NOT NULL REFERENCES raw.usage_report (source_file_id),
    rank           integer NOT NULL CHECK (rank > 0),
    pokemon        text    NOT NULL,
    usage_percent  numeric NOT NULL CHECK (usage_percent BETWEEN 0 AND 100),
    raw_count      integer NOT NULL CHECK (raw_count >= 0),
    raw_percent    numeric NOT NULL CHECK (raw_percent BETWEEN 0 AND 100),
    real_count     integer NOT NULL CHECK (real_count >= 0),
    real_percent   numeric NOT NULL CHECK (real_percent >= 0),
    PRIMARY KEY (source_file_id, pokemon)
);
