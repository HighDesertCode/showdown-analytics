-- The latest version of each Smogon file, with its team type as a Showdown ID (null for overall reports).
-- When Smogon republishes a file (same URL, new content), the newer version replaces the older one.
with ranked as (
    select
        source_file_id,
        row_number() over (partition by url order by retrieved_at desc, source_file_id desc) as version_rank
    from {{ source('raw', 'source_file') }}
)

select
    file.source_file_id,
    file.family,
    file.format,
    file.report_month,
    file.baseline,
    team_type.showdown_id as team_type,
    file.url,
    file.retrieved_at
from {{ source('raw', 'source_file') }} as file
inner join ranked on ranked.source_file_id = file.source_file_id and ranked.version_rank = 1
left join {{ source('reference', 'type') }} as team_type on team_type.type_id = file.team_type_id
