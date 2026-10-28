-- Weighted abilities per Pokémon in each current chaos report, matched to reference.ability.
select
    option.chaos_pokemon_id,
    ability.ability_id,
    option.label,
    option.weight
from {{ source('raw', 'chaos_option') }} as option
inner join {{ ref('stg_chaos_pokemon') }} as pokemon on pokemon.chaos_pokemon_id = option.chaos_pokemon_id
left join {{ source('reference', 'ability') }} as ability on ability.showdown_id = option.label
where option.category = 'abilities'
