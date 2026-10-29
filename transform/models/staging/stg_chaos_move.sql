-- Weighted moves per Pokémon in each current chaos report, matched to reference.move.
-- Smogon's empty label is an unused move slot; it keeps its weight with is_empty_slot = true.
SELECT
    option.chaos_pokemon_id,
    move.move_id,
    option.label,
    option.label = '' AS is_empty_slot,
    option.weight
FROM {{ source('raw', 'chaos_option') }} AS option
INNER JOIN {{ ref('stg_chaos_pokemon') }} AS pokemon ON pokemon.chaos_pokemon_id = option.chaos_pokemon_id
LEFT JOIN {{ source('reference', 'move') }} AS move ON move.showdown_id = option.label
WHERE option.category = 'moves'
