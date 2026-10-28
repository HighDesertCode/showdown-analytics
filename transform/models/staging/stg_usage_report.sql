-- One row per current usage report: its battle count and average weight per team.
-- avg_team_weight shows how much data a baseline rests on; very small values mean few teams carry weight.
select
    file.source_file_id,
    file.format,
    file.report_month,
    file.baseline,
    file.team_type,
    report.battle_count,
    report.avg_team_weight
from {{ source('raw', 'usage_report') }} as report
inner join {{ ref('stg_source_file') }} as file on file.source_file_id = report.source_file_id
