-- One row per ability from Showdown's abilities.js; short_description comes from Showdown's data/text/abilities.ts.
CREATE TABLE reference.ability (
    ability_id        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    showdown_id       text     NOT NULL UNIQUE CHECK (showdown_id ~ '^[a-z0-9]+$'),
    name              text     NOT NULL UNIQUE,
    num               smallint NOT NULL,
    short_description text,
    nonstandard       text
);
