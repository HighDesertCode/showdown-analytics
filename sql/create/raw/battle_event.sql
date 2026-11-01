-- One row per game event in a parsed battle, in log order. HP values are percentages of max HP, as the log shows
-- them; caused_by_seq links an effect to the move or hazard behind it, and source_inferred marks causes the parser
-- deduced rather than read from the log.
CREATE TABLE raw.battle_event (
    replay_id        TEXT     REFERENCES raw.battle (replay_id) ON DELETE CASCADE,
    seq              INTEGER  CHECK (seq > 0),
    turn             SMALLINT NOT NULL CHECK (turn >= 0),
    side             TEXT     CHECK (side IN ('p1', 'p2')),   -- NULL for field events such as weather
    pokemon          TEXT,
    event            TEXT     NOT NULL,
    detail           TEXT,
    target_side      TEXT     CHECK (target_side IN ('p1', 'p2')),
    target_pokemon   TEXT,
    damage_percent   SMALLINT CHECK (damage_percent BETWEEN 1 AND 100),
    hp_after_percent SMALLINT CHECK (hp_after_percent BETWEEN 0 AND 100),
    healed_percent   SMALLINT CHECK (healed_percent BETWEEN 1 AND 100),
    caused_by_seq    INTEGER  CHECK (caused_by_seq < seq),
    source           TEXT,
    source_inferred  BOOLEAN  NOT NULL DEFAULT FALSE,
    log_line         TEXT     NOT NULL,
    PRIMARY KEY (replay_id, seq),
    FOREIGN KEY (replay_id, caused_by_seq) REFERENCES raw.battle_event (replay_id, seq)
);
