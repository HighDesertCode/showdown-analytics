-- One row per type pairing in each current matchup chart, matched to reference.type.
-- Mirror matches are printed as 0.000%, which is not a real win rate; is_mirror marks them.
SELECT
    file.source_file_id,
    file.format,
    file.report_month,
    file.baseline,
    team_type.type_id,
    opponent_type.type_id AS opponent_type_id,
    cell.type,
    cell.opponent_type,
    cell.type = cell.opponent_type AS is_mirror,
    cell.wins,
    cell.win_percent
FROM {{ source('raw', 'matchup_chart_cell') }} AS cell
INNER JOIN {{ ref('stg_source_file') }} AS file ON file.source_file_id = cell.source_file_id
LEFT JOIN {{ source('reference', 'type') }} AS team_type ON team_type.showdown_id = cell.type
LEFT JOIN {{ source('reference', 'type') }} AS opponent_type ON opponent_type.showdown_id = cell.opponent_type
