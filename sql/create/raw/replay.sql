-- One row per public replay, as published at /{id}.json. Rows are never updated or deleted, so a replay its
-- uploader later deletes stays here; the parsed battle tables are rebuilt from log.
CREATE TABLE raw.replay (
    replay_id    TEXT        PRIMARY KEY CHECK (replay_id ~ '^[a-z0-9]+-[0-9]+$'),
    format_id    TEXT        NOT NULL CHECK (format_id ~ '^[a-z0-9]+$'),
    format       TEXT        NOT NULL,
    players      TEXT[]      NOT NULL CHECK (CARDINALITY(players) = 2),
    rating       INTEGER     CHECK (rating >= 0),
    uploaded_at  TIMESTAMPTZ NOT NULL,
    log          TEXT        NOT NULL CHECK (log <> ''),
    retrieved_at TIMESTAMPTZ NOT NULL
);
