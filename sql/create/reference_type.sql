-- One row per standard Pokémon type from Showdown's typechart.js. The Tera-only Stellar type is excluded.
CREATE TABLE reference.type (
    type_id     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    showdown_id text NOT NULL UNIQUE CHECK (showdown_id ~ '^[a-z]+$'),
    name        text NOT NULL UNIQUE
);
