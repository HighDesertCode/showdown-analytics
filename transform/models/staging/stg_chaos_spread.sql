-- Weighted EV spreads per Pokémon in each current chaos report. Smogon's label (e.g. "Timid:0/0/4/252/0/252")
-- is split into its nature, matched to reference.nature, and six EV values; the original label is kept.
with spreads as (
    select
        option.chaos_pokemon_id,
        option.label,
        option.weight,
        split_part(option.label, ':', 1) as nature_name,
        split_part(option.label, ':', 2) as evs
    from {{ source('raw', 'chaos_option') }} as option
    inner join {{ ref('stg_chaos_pokemon') }} as pokemon on pokemon.chaos_pokemon_id = option.chaos_pokemon_id
    where option.category = 'spreads'
)

select
    spreads.chaos_pokemon_id,
    nature.nature_id,
    spreads.label,
    split_part(spreads.evs, '/', 1)::smallint as hp_evs,
    split_part(spreads.evs, '/', 2)::smallint as atk_evs,
    split_part(spreads.evs, '/', 3)::smallint as def_evs,
    split_part(spreads.evs, '/', 4)::smallint as spa_evs,
    split_part(spreads.evs, '/', 5)::smallint as spd_evs,
    split_part(spreads.evs, '/', 6)::smallint as spe_evs,
    spreads.weight
from spreads
left join {{ source('reference', 'nature') }} as nature on nature.showdown_id = {{ to_id('spreads.nature_name') }}
