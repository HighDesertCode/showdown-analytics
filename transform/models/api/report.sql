-- One row per report scope: a format, month, baseline, and team type (null for overall).
-- Each report family is a separate Smogon file, so each gets its own source file column.
-- Matchup charts cover only overall teams and are linked from type_matchup instead.
WITH scope AS (
    SELECT
        format,
        report_month,
        baseline,
        team_type,
        MAX(source_file_id) FILTER (WHERE family = 'usage') AS usage_source_file_id,
        MAX(source_file_id) FILTER (WHERE family = 'chaos') AS chaos_source_file_id,
        MAX(source_file_id) FILTER (WHERE family = 'leads') AS leads_source_file_id,
        MAX(source_file_id) FILTER (WHERE family = 'metagame') AS metagame_source_file_id
    FROM {{ ref('stg_source_file') }}
    WHERE family <> 'matchup_chart'
    GROUP BY format, report_month, baseline, team_type
)

SELECT
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
FROM scope
LEFT JOIN {{ ref('stg_usage_report') }} AS usage ON usage.source_file_id = scope.usage_source_file_id
LEFT JOIN {{ ref('stg_metagame_report') }} AS metagame ON metagame.source_file_id = scope.metagame_source_file_id
