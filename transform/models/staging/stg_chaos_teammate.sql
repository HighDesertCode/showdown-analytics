-- Weighted teammates per Pokémon in each current chaos report, matched to reference.species.
-- Smogon's "empty" label is an unfilled team slot; it keeps its weight with is_empty_slot = true.
select
    option.chaos_pokemon_id,
    species.species_id as teammate_species_id,
    option.label,
    option.label = 'empty' as is_empty_slot,
    option.weight
from {{ source('raw', 'chaos_option') }} as option
inner join {{ ref('stg_chaos_pokemon') }} as pokemon on pokemon.chaos_pokemon_id = option.chaos_pokemon_id
left join {{ source('reference', 'species') }} as species on species.showdown_id = {{ to_id('option.label') }}
where option.category = 'teammates'
