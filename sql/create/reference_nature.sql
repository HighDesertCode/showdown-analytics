-- One row per nature from Showdown's data/natures.ts. Neutral natures have no stat changes.
CREATE TABLE reference.nature (
    nature_id      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    showdown_id    text NOT NULL UNIQUE CHECK (showdown_id ~ '^[a-z]+$'),
    name           text NOT NULL UNIQUE,
    increased_stat text CHECK (increased_stat IN ('atk', 'def', 'spa', 'spd', 'spe')),
    decreased_stat text CHECK (decreased_stat IN ('atk', 'def', 'spa', 'spd', 'spe')),
    CONSTRAINT nature_stat_pairing CHECK ((increased_stat IS NULL) = (decreased_stat IS NULL)),
    CONSTRAINT nature_stats_distinct CHECK (increased_stat <> decreased_stat)
);
