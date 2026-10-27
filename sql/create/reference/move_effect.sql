-- One row per move effect from moves.json: guaranteed effects (top-level and `self`) and
-- chance-based secondary effects (`secondary`/`secondaries`).
-- Rows with no effect columns set (e.g. Tri Attack) are effects Showdown implements in code;
-- see reference.move.short_description for what they do.
CREATE TABLE reference.move_effect (
    move_id         bigint   NOT NULL REFERENCES reference.move (move_id),
    effect_number   smallint NOT NULL CHECK (effect_number >= 1),
    is_secondary    boolean  NOT NULL,  -- false = always happens; true = chance-based
    chance          smallint NOT NULL CHECK (chance BETWEEN 1 AND 100),  -- 100 for guaranteed effects
    affects         text     NOT NULL CHECK (affects IN ('target', 'self', 'field')),
    status          text     CHECK (status IN ('brn', 'par', 'psn', 'tox', 'frz', 'slp')),
    volatile_status text,    -- e.g. flinch, confusion, protect
    field_effect    text     CHECK (field_effect ~ '^[a-z]+$'),  -- e.g. stealthrock, raindance, trickroom
    atk_stages      smallint CHECK (atk_stages BETWEEN -6 AND 6),
    def_stages      smallint CHECK (def_stages BETWEEN -6 AND 6),
    spa_stages      smallint CHECK (spa_stages BETWEEN -6 AND 6),
    spd_stages      smallint CHECK (spd_stages BETWEEN -6 AND 6),
    spe_stages      smallint CHECK (spe_stages BETWEEN -6 AND 6),
    accuracy_stages smallint CHECK (accuracy_stages BETWEEN -6 AND 6),
    evasion_stages  smallint CHECK (evasion_stages BETWEEN -6 AND 6),
    PRIMARY KEY (move_id, effect_number)
);
