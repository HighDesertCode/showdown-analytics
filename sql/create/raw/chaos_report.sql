-- One row per chaos JSON file: the file's "info" block.
CREATE TABLE raw.chaos_report (
    source_file_id   bigint  PRIMARY KEY REFERENCES raw.source_file (source_file_id),
    metagame         text    NOT NULL,
    cutoff           integer NOT NULL,
    cutoff_deviation integer NOT NULL,
    team_type        text,
    battle_count     integer NOT NULL CHECK (battle_count >= 0)
);
