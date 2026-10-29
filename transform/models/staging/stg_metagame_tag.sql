-- One row per tag in each current metagame report. Type tags (e.g. "monowater") also get the type's Showdown ID
-- in tag_team_type; style, weather, and strategy tags (e.g. "stall", "sand") leave it null.
SELECT
    file.source_file_id,
    file.format,
    file.report_month,
    file.baseline,
    file.team_type,
    tag.tag,
    tag_type.showdown_id AS tag_team_type,
    tag.percent
FROM {{ source('raw', 'metagame_tag') }} AS tag
INNER JOIN {{ ref('stg_source_file') }} AS file ON file.source_file_id = tag.source_file_id
LEFT JOIN {{ source('reference', 'type') }} AS tag_type ON 'mono' || tag_type.showdown_id = tag.tag
