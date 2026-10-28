-- Weighted moves per Pokémon in each current chaos report, matched to reference.move.
-- Smogon's empty label is an unused move slot; it keeps its weight with is_empty_slot = true.
select
    option.chaos_pokemon_id,
    move.move_id,
    option.label,
    option.label = '' as is_empty_slot,
    option.weight
from {{ source('raw', 'chaos_option') }} as option
inner join {{ ref('stg_chaos_pokemon') }} as pokemon on pokemon.chaos_pokemon_id = option.chaos_pokemon_id
left join {{ source('reference', 'move') }} as move on move.showdown_id = option.label
where option.category = 'moves'
