-- Team preview, in the order shown.
CREATE TABLE raw.battle_pokemon (
    replay_id TEXT     REFERENCES raw.battle (replay_id) ON DELETE CASCADE,
    side      TEXT     CHECK (side IN ('p1', 'p2')),
    slot      SMALLINT CHECK (slot BETWEEN 1 AND 6),
    species   TEXT     NOT NULL,                              -- as previewed, e.g. "Urshifu-*" hides the form
    nickname  TEXT,                                           -- NULL if it never switched in
    PRIMARY KEY (replay_id, side, slot)
);
