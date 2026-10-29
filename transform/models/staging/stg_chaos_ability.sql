-- Weighted abilities per Pokémon in each current chaos report, matched to reference.ability.
SELECT
    option.chaos_pokemon_id,
    ability.ability_id,
    option.label,
    option.weight
FROM {{ source('raw', 'chaos_option') }} AS option
INNER JOIN {{ ref('stg_chaos_pokemon') }} AS pokemon ON pokemon.chaos_pokemon_id = option.chaos_pokemon_id
LEFT JOIN {{ source('reference', 'ability') }} AS ability ON ability.showdown_id = option.label
WHERE option.category = 'abilities'
