-- One row per Pokémon in each current usage report, matched to reference.species.
-- Percentages stay as published (0 to 100); real_percent sums to 600% and can exceed 100.
select
    file.source_file_id,
    file.format,
    file.report_month,
    file.baseline,
    file.team_type,
    species.species_id,
    pokemon.pokemon as pokemon_name,
    pokemon.rank,
    pokemon.usage_percent,
    pokemon.raw_count,
    pokemon.raw_percent,
    pokemon.real_count,
    pokemon.real_percent,
    report.battle_count,
    report.avg_team_weight
from {{ source('raw', 'usage_pokemon') }} as pokemon
inner join {{ ref('stg_source_file') }} as file on file.source_file_id = pokemon.source_file_id
inner join {{ source('raw', 'usage_report') }} as report on report.source_file_id = pokemon.source_file_id
left join {{ source('reference', 'species') }} as species on species.showdown_id = {{ to_id('pokemon.pokemon') }}
