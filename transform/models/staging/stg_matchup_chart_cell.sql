-- One row per type pairing in each current matchup chart, matched to reference.type.
-- Mirror matches are printed as 0.000%, which is not a real win rate; is_mirror marks them.
select
    file.source_file_id,
    file.format,
    file.report_month,
    file.baseline,
    team_type.type_id,
    opponent_type.type_id as opponent_type_id,
    cell.type,
    cell.opponent_type,
    cell.type = cell.opponent_type as is_mirror,
    cell.wins,
    cell.win_percent
from {{ source('raw', 'matchup_chart_cell') }} as cell
inner join {{ ref('stg_source_file') }} as file on file.source_file_id = cell.source_file_id
left join {{ source('reference', 'type') }} as team_type on team_type.showdown_id = cell.type
left join {{ source('reference', 'type') }} as opponent_type on opponent_type.showdown_id = cell.opponent_type
