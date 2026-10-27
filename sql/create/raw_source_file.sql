-- One row per Smogon file retrieved. Every raw row links back to the file it was loaded from.
-- A republished file (same URL, new content) gets a new row; dbt uses the latest one per URL.
CREATE TABLE raw.source_file (
    source_file_id bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    url            text        NOT NULL CHECK (url LIKE 'https://www.smogon.com/stats/%'),
    family         text        NOT NULL CHECK (family IN ('chaos', 'usage', 'leads', 'metagame', 'matchup_chart')),
    format         text        NOT NULL CHECK (format ~ '^[a-z0-9]+$'),
    report_month   date        NOT NULL CHECK (extract(day FROM report_month) = 1),
    baseline       integer     NOT NULL CHECK (baseline IN (0, 1500, 1630, 1760)),
    team_type_id   bigint      REFERENCES reference.type (type_id),
    content_sha256 text        NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    byte_size      integer     NOT NULL CHECK (byte_size > 0),
    retrieved_at   timestamptz NOT NULL,
    CONSTRAINT source_file_content_unique UNIQUE (url, content_sha256)
);
