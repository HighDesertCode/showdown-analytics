-- One row per Pokémon in each current leads report, matched to reference.species.
-- Percentages stay as published; each sums to 100% within a report.
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
    report.lead_count
from {{ source('raw', 'leads_pokemon') }} as pokemon
inner join {{ ref('stg_source_file') }} as file on file.source_file_id = pokemon.source_file_id
inner join {{ source('raw', 'leads_report') }} as report on report.source_file_id = pokemon.source_file_id
left join {{ source('reference', 'species') }} as species on species.showdown_id = {{ to_id('pokemon.pokemon') }}
