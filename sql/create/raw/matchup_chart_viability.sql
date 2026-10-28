-- One row per type in a matchup chart's "Type Ranking" section: Smogon's published ViabilityScore,
-- a source-defined score that is not a win rate.
CREATE TABLE raw.matchup_chart_viability (
    source_file_id  bigint  NOT NULL REFERENCES raw.matchup_chart_report (source_file_id),
    type            text    NOT NULL CHECK (type ~ '^[a-z]+$'),
    viability_score numeric NOT NULL,
    PRIMARY KEY (source_file_id, type)
);
