-- One row per Pokémon in each report scope: usage from the usage report, plus the viability ceiling from chaos.
-- Smogon's percentages become 0-to-1 proportions:
--   usage_share: weighted share of teams with this Pokémon (usage % / 100)
--   raw_share:   unweighted share of teams with this Pokémon (raw % / 100)
--   real_share:  share of all Pokémon brought into battle (real % / 600, since Smogon scales real % to sum to 600)
-- Chaos omits Pokémon with negligible weight, so their viability columns are null.
select
    usage.format,
    usage.report_month,
    usage.baseline,
    usage.team_type,
    species.species_id,
    species.showdown_id as species,
    species.name as species_name,
    usage.rank,
    trim_scale(usage.usage_percent / 100) as usage_share,
    usage.raw_count,
    trim_scale(usage.raw_percent / 100) as raw_share,
    usage.real_count,
    trim_scale(round(usage.real_percent / 600, 8)) as real_share,
    chaos.viability_user_count,
    chaos.viability_top_gxe,
    chaos.viability_gxe_p99,
    chaos.viability_gxe_p95,
    usage.source_file_id as usage_source_file_id,
    chaos.source_file_id as chaos_source_file_id
from {{ ref('stg_usage_pokemon') }} as usage
inner join {{ source('reference', 'species') }} as species on species.species_id = usage.species_id
left join {{ ref('stg_chaos_pokemon') }} as chaos
    on chaos.format = usage.format
    and chaos.report_month = usage.report_month
    and chaos.baseline = usage.baseline
    and chaos.team_type is not distinct from usage.team_type
    and chaos.species_id = usage.species_id
