-- One row per usage text report: the "Total battles" and "Avg. weight/team" header lines.
-- avg_team_weight is the total team weight divided by all teams in the format, even in per-type reports.
CREATE TABLE raw.usage_report (
    source_file_id  bigint  PRIMARY KEY REFERENCES raw.source_file (source_file_id),
    battle_count    integer NOT NULL CHECK (battle_count >= 0),
    avg_team_weight numeric NOT NULL CHECK (avg_team_weight >= 0)
);
