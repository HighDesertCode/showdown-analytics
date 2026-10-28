-- Checks and counters per Pokémon in each current overall chaos report, matched to reference.species.
-- Smogon's n, p, and d: weighted encounters, the share of encounters where the Pokémon was KOed or forced
-- to switch out by the opponent, and that share's standard deviation. Smogon ranks counters by p - 4d.
select
    counter.chaos_pokemon_id,
    species.species_id as opponent_species_id,
    counter.opponent as opponent_name,
    counter.n as encounters,
    counter.p as ko_or_switch_rate,
    counter.d as ko_or_switch_rate_std_dev,
    counter.p - 4 * counter.d as score
from {{ source('raw', 'chaos_counter') }} as counter
inner join {{ ref('stg_chaos_pokemon') }} as pokemon on pokemon.chaos_pokemon_id = counter.chaos_pokemon_id
left join {{ source('reference', 'species') }} as species on species.showdown_id = {{ to_id('counter.opponent') }}
