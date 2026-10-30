-- One row per `load-smogon` run: inserted as running when it starts, then updated after each file and at the end.
-- A row still running long after started_at means the run was killed before it could record its result.
CREATE TABLE raw.ingestion_run (
    ingestion_run_id BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    report_month     DATE        NOT NULL CHECK (EXTRACT(DAY FROM report_month) = 1),
    families         TEXT[]      NOT NULL CHECK (CARDINALITY(families) > 0),
    started_at       TIMESTAMPTZ NOT NULL,
    finished_at      TIMESTAMPTZ CHECK (finished_at >= started_at),
    status           TEXT        NOT NULL CHECK (status IN ('running', 'succeeded', 'partial', 'failed')),
    files_loaded     INTEGER     NOT NULL DEFAULT 0 CHECK (files_loaded >= 0),
    files_skipped    INTEGER     NOT NULL DEFAULT 0 CHECK (files_skipped >= 0),
    files_failed     INTEGER     NOT NULL DEFAULT 0 CHECK (files_failed >= 0),
    error            TEXT,
    CONSTRAINT ingestion_run_finished CHECK ((status = 'running') = (finished_at IS NULL)),
    CONSTRAINT ingestion_run_error CHECK ((status = 'failed') = (error IS NOT NULL))
);
