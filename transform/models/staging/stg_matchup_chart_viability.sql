-- Smogon's published ViabilityScore per type in each current matchup chart, matched to reference.type.
select
    file.source_file_id,
    file.format,
    file.report_month,
    file.baseline,
    team_type.type_id,
    viability.type,
    viability.viability_score
from {{ source('raw', 'matchup_chart_viability') }} as viability
inner join {{ ref('stg_source_file') }} as file on file.source_file_id = viability.source_file_id
left join {{ source('reference', 'type') }} as team_type on team_type.showdown_id = viability.type
