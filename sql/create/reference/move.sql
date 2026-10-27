-- One row per move from Showdown's moves.json; short_description comes from Showdown's data/text/moves.ts.
-- accuracy is NULL for moves that cannot miss (Showdown uses `true`).
CREATE TABLE reference.move (
    move_id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    showdown_id       text     NOT NULL UNIQUE CHECK (showdown_id ~ '^[a-z0-9]+$'),
    name              text     NOT NULL UNIQUE,
    num               smallint NOT NULL,
    type_id           bigint   NOT NULL REFERENCES reference.type (type_id),
    category          text     NOT NULL CHECK (category IN ('Physical', 'Special', 'Status')),
    base_power        smallint NOT NULL CHECK (base_power >= 0),
    accuracy          smallint CHECK (accuracy BETWEEN 1 AND 100),
    pp                smallint NOT NULL CHECK (pp >= 1),
    priority          smallint NOT NULL CHECK (priority BETWEEN -7 AND 5),
    target            text     NOT NULL,  -- e.g. normal, self, allAdjacentFoes
    short_description text,
    nonstandard       text
);
