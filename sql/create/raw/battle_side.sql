-- Each player in a parsed battle, with their ladder Elo (not Smogon's Glicko) from the log's rating lines.
CREATE TABLE raw.battle_side (
    replay_id  TEXT     REFERENCES raw.battle (replay_id) ON DELETE CASCADE,
    side       TEXT     CHECK (side IN ('p1', 'p2')),
    player     TEXT     NOT NULL,
    elo_before SMALLINT CHECK (elo_before > 0),               -- from the |raw| rating lines; NULL if unrated
    elo_after  SMALLINT CHECK (elo_after > 0),
    result     TEXT     NOT NULL CHECK (result IN ('win', 'loss', 'tie')),
    PRIMARY KEY (replay_id, side)
);
