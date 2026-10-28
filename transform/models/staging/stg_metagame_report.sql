-- One row per current metagame report: its average stalliness (negative = offensive, positive = stall).
select
    file.source_file_id,
    file.format,
    file.report_month,
    file.baseline,
    file.team_type,
    report.stalliness_mean
from {{ source('raw', 'metagame_report') }} as report
inner join {{ ref('stg_source_file') }} as file on file.source_file_id = report.source_file_id
