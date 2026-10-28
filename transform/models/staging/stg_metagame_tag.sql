-- One row per tag in each current metagame report. Type tags (e.g. "monowater") also get the type's Showdown ID
-- in tag_team_type; style, weather, and strategy tags (e.g. "stall", "sand") leave it null.
select
    file.source_file_id,
    file.format,
    file.report_month,
    file.baseline,
    file.team_type,
    tag.tag,
    tag_type.showdown_id as tag_team_type,
    tag.percent
from {{ source('raw', 'metagame_tag') }} as tag
inner join {{ ref('stg_source_file') }} as file on file.source_file_id = tag.source_file_id
left join {{ source('reference', 'type') }} as tag_type on 'mono' || tag_type.showdown_id = tag.tag
