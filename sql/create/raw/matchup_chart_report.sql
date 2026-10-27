-- One row per Monotype matchup chart file (overall only, one per baseline). The file's title only repeats
-- the baseline, which the loader checks against the URL, so this table holds no columns of its own.
CREATE TABLE raw.matchup_chart_report (
    source_file_id bigint PRIMARY KEY REFERENCES raw.source_file (source_file_id)
);
