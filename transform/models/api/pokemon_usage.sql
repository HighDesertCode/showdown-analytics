-- One row per Pokémon in each report scope: usage from the usage report, plus the viability ceiling from chaos.
-- Smogon's percentages become 0-to-1 proportions:
--   usage_share: weighted share of teams with this Pokémon (usage % / 100)
--   raw_share:   unweighted share of teams with this Pokémon (raw % / 100)
--   real_share:  share of all Pokémon brought into battle (real % / 600, since Smogon scales real % to sum to 600)
-- Chaos omits Pokémon with negligible weight, so their viability columns are null.
SELECT
    usage.format,
    usage.report_month,
    usage.baseline,
    usage.team_type,
    species.species_id,
    species.showdown_id AS species,
    species.name AS species_name,
    usage.rank,
    TRIM_SCALE(usage.usage_percent / 100) AS usage_share,
    usage.raw_count,
    TRIM_SCALE(usage.raw_percent / 100) AS raw_share,
    usage.real_count,
    TRIM_SCALE(ROUND(usage.real_percent / 600, 8)) AS real_share,
    chaos.viability_user_count,
    chaos.viability_top_gxe,
    chaos.viability_gxe_p99,
    chaos.viability_gxe_p95,
    usage.source_file_id AS usage_source_file_id,
    chaos.source_file_id AS chaos_source_file_id
FROM {{ ref('stg_usage_pokemon') }} AS usage
INNER JOIN {{ source('reference', 'species') }} AS species ON species.species_id = usage.species_id
LEFT JOIN {{ ref('stg_chaos_pokemon') }} AS chaos
    ON chaos.format = usage.format
    AND chaos.report_month = usage.report_month
    AND chaos.baseline = usage.baseline
    AND chaos.team_type IS NOT DISTINCT FROM usage.team_type
    AND chaos.species_id = usage.species_id
