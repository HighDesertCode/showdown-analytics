-- One row per parsed replay. Deleting it deletes its sides, Pokémon, and events, so a replay is re-parsed by
-- deleting its battle and inserting the new parse in one transaction.
CREATE TABLE raw.battle (
    replay_id  TEXT        PRIMARY KEY REFERENCES raw.replay (replay_id),
    rated      BOOLEAN     NOT NULL,                          -- the |rated| line
    started_at TIMESTAMPTZ NOT NULL,                          -- the first |t:| line
    ended_at   TIMESTAMPTZ NOT NULL CHECK (ended_at >= started_at),
    turns      SMALLINT    NOT NULL CHECK (turns >= 0),
    winner     TEXT        CHECK (winner IN ('p1', 'p2')),    -- NULL for a tie
    ended_by   TEXT        NOT NULL CHECK (ended_by IN ('knockout', 'forfeit', 'inactivity', 'tie')),
    rules      TEXT[]      NOT NULL,
    parsed_at  TIMESTAMPTZ NOT NULL
);
