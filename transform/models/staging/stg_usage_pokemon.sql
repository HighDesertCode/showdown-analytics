-- One row per Pokémon in each current usage report, matched to reference.species.
-- Percentages stay as published (0 to 100); real_percent sums to 600% and can exceed 100.
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
    pokemon.real_count,
    pokemon.real_percent,
    report.battle_count,
    report.avg_team_weight
FROM {{ source('raw', 'usage_pokemon') }} AS pokemon
INNER JOIN {{ ref('stg_source_file') }} AS file ON file.source_file_id = pokemon.source_file_id
INNER JOIN {{ source('raw', 'usage_report') }} AS report ON report.source_file_id = pokemon.source_file_id
LEFT JOIN {{ source('reference', 'species') }} AS species ON species.showdown_id = {{ to_id('pokemon.pokemon') }}
