-- Weighted items per Pokémon in each current chaos report, matched to reference.item.
-- Smogon's "nothing" label means no held item; it keeps its weight with has_item = false.
SELECT
    option.chaos_pokemon_id,
    item.item_id,
    option.label,
    option.label <> 'nothing' AS has_item,
    option.weight
FROM {{ source('raw', 'chaos_option') }} AS option
INNER JOIN {{ ref('stg_chaos_pokemon') }} AS pokemon ON pokemon.chaos_pokemon_id = option.chaos_pokemon_id
LEFT JOIN {{ source('reference', 'item') }} AS item ON item.showdown_id = option.label
WHERE option.category = 'items'
