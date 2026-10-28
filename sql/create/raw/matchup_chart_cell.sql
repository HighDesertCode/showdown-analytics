-- One row per type pairing in a matchup chart: the row type's weighted wins and win percent against the
-- opponent type, as printed. Mirror matches (e.g. water vs water) are printed as 0.000% and stored that way.
CREATE TABLE raw.matchup_chart_cell (
    source_file_id bigint  NOT NULL REFERENCES raw.matchup_chart_report (source_file_id),
    type           text    NOT NULL CHECK (type ~ '^[a-z]+$'),
    opponent_type  text    NOT NULL CHECK (opponent_type ~ '^[a-z]+$'),
    wins           numeric NOT NULL CHECK (wins >= 0),
    win_percent    numeric NOT NULL CHECK (win_percent BETWEEN 0 AND 100),
    PRIMARY KEY (source_file_id, type, opponent_type)
);
