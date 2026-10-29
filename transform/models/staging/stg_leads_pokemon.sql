-- One row per Pokémon in each current leads report, matched to reference.species.
-- Percentages stay as published; each sums to 100% within a report.
SELECT
    file.source_file_id,
    file.format,
    file.report_month,
    file.baseline,
    file.team_type,
    species.species_id,
    pokemon.pokemon AS pokemon_name,
    pokemon.rank,
    pokemon.usage_percent,
    pokemon.raw_count,
    pokemon.raw_percent,
    report.lead_count
FROM {{ source('raw', 'leads_pokemon') }} AS pokemon
INNER JOIN {{ ref('stg_source_file') }} AS file ON file.source_file_id = pokemon.source_file_id
INNER JOIN {{ source('raw', 'leads_report') }} AS report ON report.source_file_id = pokemon.source_file_id
LEFT JOIN {{ source('reference', 'species') }} AS species ON species.showdown_id = {{ to_id('pokemon.pokemon') }}
