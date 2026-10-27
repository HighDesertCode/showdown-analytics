-- One row per item from Showdown's items.js; short_description comes from Showdown's data/text/items.ts.
CREATE TABLE reference.item (
    item_id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    showdown_id       text     NOT NULL UNIQUE CHECK (showdown_id ~ '^[a-z0-9]+$'),
    name              text     NOT NULL UNIQUE,
    num               smallint NOT NULL,
    is_berry          boolean  NOT NULL,
    short_description text,
    nonstandard       text
);
