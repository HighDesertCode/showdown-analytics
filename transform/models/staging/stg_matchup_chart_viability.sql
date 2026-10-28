-- Smogon's published ViabilityScore per type in each current matchup chart, matched to reference.type.
SELECT
    file.source_file_id,
    file.format,
    file.report_month,
    file.baseline,
    team_type.type_id,
    viability.type,
    viability.viability_score
FROM {{ source('raw', 'matchup_chart_viability') }} AS viability
INNER JOIN {{ ref('stg_source_file') }} AS file ON file.source_file_id = viability.source_file_id
LEFT JOIN {{ source('reference', 'type') }} AS team_type ON team_type.showdown_id = viability.type
