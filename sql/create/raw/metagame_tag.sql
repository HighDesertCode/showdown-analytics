-- One row per tag in a metagame report (e.g. "stall", "sand", "monowater"), with its percent as printed.
-- A team can carry several tags, so a report's percentages sum to well over 100%.
CREATE TABLE raw.metagame_tag (
    source_file_id bigint  NOT NULL REFERENCES raw.metagame_report (source_file_id),
    tag            text    NOT NULL CHECK (tag ~ '^[a-z0-9]+$'),
    percent        numeric NOT NULL CHECK (percent BETWEEN 0 AND 100),
    PRIMARY KEY (source_file_id, tag)
);
