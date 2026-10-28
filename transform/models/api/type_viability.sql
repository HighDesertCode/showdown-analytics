-- Smogon's ViabilityScore per type, from overall matchup charts, with its rank (1 = highest score).
-- It is Smogon's published score, not a win rate.
SELECT
    viability.format,
    viability.report_month,
    viability.baseline,
    team_type.type_id,
    team_type.showdown_id AS type,
    team_type.name AS type_name,
    viability.viability_score,
    RANK() OVER (PARTITION BY viability.source_file_id ORDER BY viability.viability_score DESC)::INTEGER AS rank,
    viability.source_file_id
FROM {{ ref('stg_matchup_chart_viability') }} AS viability
INNER JOIN {{ source('reference', 'type') }} AS team_type ON team_type.type_id = viability.type_id
