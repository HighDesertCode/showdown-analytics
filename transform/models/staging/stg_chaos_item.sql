-- Weighted items per Pokémon in each current chaos report, matched to reference.item.
-- Smogon's "nothing" label means no held item; it keeps its weight with has_item = false.
select
    option.chaos_pokemon_id,
    item.item_id,
    option.label,
    option.label <> 'nothing' as has_item,
    option.weight
from {{ source('raw', 'chaos_option') }} as option
inner join {{ ref('stg_chaos_pokemon') }} as pokemon on pokemon.chaos_pokemon_id = option.chaos_pokemon_id
left join {{ source('reference', 'item') }} as item on item.showdown_id = option.label
where option.category = 'items'
