-- One row per `collect-replays` run: inserted as running when it starts, then updated after each replay and at
-- the end. A row still running long after started_at means the run was killed before it could record its result.
CREATE TABLE raw.replay_collection_run (
    replay_collection_run_id BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    format_id                TEXT        NOT NULL CHECK (format_id ~ '^[a-z0-9]+$'),
    started_at               TIMESTAMPTZ NOT NULL,
    finished_at              TIMESTAMPTZ CHECK (finished_at >= started_at),
    status                   TEXT        NOT NULL CHECK (status IN ('running', 'succeeded', 'partial', 'failed')),
    replays_loaded           INTEGER     NOT NULL DEFAULT 0 CHECK (replays_loaded >= 0),
    replays_failed           INTEGER     NOT NULL DEFAULT 0 CHECK (replays_failed >= 0),
    error                    TEXT,
    CONSTRAINT replay_collection_run_finished CHECK ((status = 'running') = (finished_at IS NULL)),
    CONSTRAINT replay_collection_run_error CHECK ((status = 'failed') = (error IS NOT NULL))
);
