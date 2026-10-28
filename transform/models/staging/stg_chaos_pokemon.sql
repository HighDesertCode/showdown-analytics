-- One row per Pokémon in each current chaos report, matched to reference.species.
-- ability_weight_total is the denominator for every option percentage: an option's weight divided by it
-- matches Smogon's moveset reports (e.g. water Swampert's Leftovers: 848.989 / 1429.394 = 59.395%).
WITH ability_weights AS (
    SELECT chaos_pokemon_id, SUM(weight) AS ability_weight_total
    FROM {{ source('raw', 'chaos_option') }}
    WHERE category = 'abilities'
    GROUP BY chaos_pokemon_id
)

SELECT
    pokemon.chaos_pokemon_id,
    file.source_file_id,
    file.format,
    file.report_month,
    file.baseline,
    file.team_type,
    species.species_id,
    pokemon.pokemon AS pokemon_name,
    pokemon.raw_count,
    pokemon.usage,
    ability_weights.ability_weight_total,
    pokemon.viability_user_count,
    pokemon.viability_top_gxe,
    pokemon.viability_gxe_p99,
    pokemon.viability_gxe_p95,
    report.battle_count
FROM {{ source('raw', 'chaos_pokemon') }} AS pokemon
INNER JOIN {{ ref('stg_source_file') }} AS file ON file.source_file_id = pokemon.source_file_id
INNER JOIN {{ source('raw', 'chaos_report') }} AS report ON report.source_file_id = pokemon.source_file_id
LEFT JOIN ability_weights ON ability_weights.chaos_pokemon_id = pokemon.chaos_pokemon_id
LEFT JOIN {{ source('reference', 'species') }} AS species ON species.showdown_id = {{ to_id('pokemon.pokemon') }}
