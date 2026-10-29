-- One row per current metagame report: its average stalliness (negative = offensive, positive = stall).
SELECT
    file.source_file_id,
    file.format,
    file.report_month,
    file.baseline,
    file.team_type,
    report.stalliness_mean
FROM {{ source('raw', 'metagame_report') }} AS report
INNER JOIN {{ ref('stg_source_file') }} AS file ON file.source_file_id = report.source_file_id
