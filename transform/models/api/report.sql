-- One row per report scope: a format, month, baseline, and team type (null for overall).
-- Each report family is a separate Smogon file, so each gets its own source file column.
-- Matchup charts cover only overall teams and are linked from type_matchup instead.
with scope as (
    select
        format,
        report_month,
        baseline,
        team_type,
        max(source_file_id) filter (where family = 'usage') as usage_source_file_id,
        max(source_file_id) filter (where family = 'chaos') as chaos_source_file_id,
        max(source_file_id) filter (where family = 'leads') as leads_source_file_id,
        max(source_file_id) filter (where family = 'metagame') as metagame_source_file_id
    from {{ ref('stg_source_file') }}
    where family <> 'matchup_chart'
    group by format, report_month, baseline, team_type
)

select
    scope.format,
    scope.report_month,
    scope.baseline,
    scope.team_type,
    usage.battle_count,
    usage.avg_team_weight,
    metagame.stalliness_mean,
    scope.usage_source_file_id,
    scope.chaos_source_file_id,
    scope.leads_source_file_id,
    scope.metagame_source_file_id
from scope
left join {{ ref('stg_usage_report') }} as usage on usage.source_file_id = scope.usage_source_file_id
left join {{ ref('stg_metagame_report') }} as metagame on metagame.source_file_id = scope.metagame_source_file_id
