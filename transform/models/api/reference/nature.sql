-- Natures from Pokémon Showdown and the stats they raise and lower (null for neutral natures).
SELECT
    nature.nature_id,
    nature.showdown_id AS nature,
    nature.name AS nature_name,
    nature.increased_stat,
    nature.decreased_stat
FROM {{ source('reference', 'nature') }} AS nature
