-- One row per metagame text report. stalliness_mean is the "Stalliness (mean: 1.730)" line: negative means
-- more offensive teams, positive more stall. The stalliness histogram bars are validated but not stored.
CREATE TABLE raw.metagame_report (
    source_file_id  bigint  PRIMARY KEY REFERENCES raw.source_file (source_file_id),
    stalliness_mean numeric NOT NULL
);
