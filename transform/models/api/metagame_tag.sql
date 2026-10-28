-- Share of teams with each metagame tag, per report scope. A team can carry several tags
-- (e.g. monoice, hail, and stall), so shares don't sum to 1. Type tags (e.g. monoice) also get the type's
-- Showdown ID in tag_team_type; style, weather, and strategy tags leave it null.
SELECT
    tag.format,
    tag.report_month,
    tag.baseline,
    tag.team_type,
    tag.tag,
    tag.tag_team_type,
    TRIM_SCALE(tag.percent / 100) AS share,
    tag.source_file_id
FROM {{ ref('stg_metagame_tag') }} AS tag
