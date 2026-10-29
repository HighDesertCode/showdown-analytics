-- Weighted teammates per Pokémon in each current chaos report, matched to reference.species.
-- Smogon's "empty" label is an unfilled team slot; it keeps its weight with is_empty_slot = true.
SELECT
    option.chaos_pokemon_id,
    species.species_id AS teammate_species_id,
    option.label,
    option.label = 'empty' AS is_empty_slot,
    option.weight
FROM {{ source('raw', 'chaos_option') }} AS option
INNER JOIN {{ ref('stg_chaos_pokemon') }} AS pokemon ON pokemon.chaos_pokemon_id = option.chaos_pokemon_id
LEFT JOIN {{ source('reference', 'species') }} AS species ON species.showdown_id = {{ to_id('option.label') }}
WHERE option.category = 'teammates'
