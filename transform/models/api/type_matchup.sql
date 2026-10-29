-- Weighted wins and win rate for each type against each other type, from overall matchup charts.
-- win_rate is wins / (wins + the opponent's wins) in that pairing. Smogon prints mirror matches as 0%,
-- so their win_rate is null.
SELECT
    cell.format,
    cell.report_month,
    cell.baseline,
    team_type.type_id,
    team_type.showdown_id AS type,
    team_type.name AS type_name,
    opponent_type.type_id AS opponent_type_id,
    opponent_type.showdown_id AS opponent_type,
    opponent_type.name AS opponent_type_name,
    cell.is_mirror,
    cell.wins,
    CASE WHEN NOT cell.is_mirror THEN TRIM_SCALE(cell.win_percent / 100) END AS win_rate,
    cell.source_file_id
FROM {{ ref('stg_matchup_chart_cell') }} AS cell
INNER JOIN {{ source('reference', 'type') }} AS team_type ON team_type.type_id = cell.type_id
INNER JOIN {{ source('reference', 'type') }} AS opponent_type ON opponent_type.type_id = cell.opponent_type_id
