-- Share of each Pokémon's sets holding each item, per report scope. Shares sum to 1 per Pokémon.
-- Sets with no held item are one row with has_item = false and null item columns.
SELECT
    pokemon.format,
    pokemon.report_month,
    pokemon.baseline,
    pokemon.team_type,
    species.species_id,
    species.showdown_id AS species,
    species.name AS species_name,
    option.has_item,
    item.item_id,
    item.showdown_id AS item,
    item.name AS item_name,
    TRIM_SCALE(ROUND((option.weight / pokemon.ability_weight_total)::NUMERIC, 10)) AS share,
    pokemon.source_file_id
FROM {{ ref('stg_chaos_item') }} AS option
INNER JOIN {{ ref('stg_chaos_pokemon') }} AS pokemon ON pokemon.chaos_pokemon_id = option.chaos_pokemon_id
INNER JOIN {{ source('reference', 'species') }} AS species ON species.species_id = pokemon.species_id
LEFT JOIN {{ source('reference', 'item') }} AS item ON item.item_id = option.item_id
