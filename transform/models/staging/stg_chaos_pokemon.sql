-- One row per Pokémon in each current chaos report, matched to reference.species.
-- ability_weight_total is the denominator for every option percentage: an option's weight divided by it
-- matches Smogon's moveset reports (e.g. water Swampert's Leftovers: 848.989 / 1429.394 = 59.395%).
with ability_weights as (
    select chaos_pokemon_id, sum(weight) as ability_weight_total
    from {{ source('raw', 'chaos_option') }}
    where category = 'abilities'
    group by chaos_pokemon_id
)

select
    pokemon.chaos_pokemon_id,
    file.source_file_id,
    file.format,
    file.report_month,
    file.baseline,
    file.team_type,
    species.species_id,
    pokemon.pokemon as pokemon_name,
    pokemon.raw_count,
    pokemon.usage,
    ability_weights.ability_weight_total,
    pokemon.viability_user_count,
    pokemon.viability_top_gxe,
    pokemon.viability_gxe_p99,
    pokemon.viability_gxe_p95,
    report.battle_count
from {{ source('raw', 'chaos_pokemon') }} as pokemon
inner join {{ ref('stg_source_file') }} as file on file.source_file_id = pokemon.source_file_id
inner join {{ source('raw', 'chaos_report') }} as report on report.source_file_id = pokemon.source_file_id
left join ability_weights on ability_weights.chaos_pokemon_id = pokemon.chaos_pokemon_id
left join {{ source('reference', 'species') }} as species on species.showdown_id = {{ to_id('pokemon.pokemon') }}
