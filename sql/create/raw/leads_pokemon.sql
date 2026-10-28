-- One row per Pokémon in a leads report, with values as printed. Only usage_percent is weighted by the baseline.
-- Each team has one lead, so both percentage columns sum to 100% within a report.
CREATE TABLE raw.leads_pokemon (
    source_file_id bigint  NOT NULL REFERENCES raw.leads_report (source_file_id),
    rank           integer NOT NULL CHECK (rank > 0),
    pokemon        text    NOT NULL,
    usage_percent  numeric NOT NULL CHECK (usage_percent BETWEEN 0 AND 100),
    raw_count      integer NOT NULL CHECK (raw_count >= 0),
    raw_percent    numeric NOT NULL CHECK (raw_percent BETWEEN 0 AND 100),
    PRIMARY KEY (source_file_id, pokemon)
);
