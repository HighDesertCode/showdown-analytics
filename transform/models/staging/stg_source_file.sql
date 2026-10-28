-- The latest version of each Smogon file, with its team type as a Showdown ID (null for overall reports).
-- When Smogon republishes a file (same URL, new content), the newer version replaces the older one.
WITH ranked AS (
    SELECT
        source_file_id,
        ROW_NUMBER() OVER (PARTITION BY url ORDER BY retrieved_at DESC, source_file_id DESC) AS version_rank
    FROM {{ source('raw', 'source_file') }}
)

SELECT
    file.source_file_id,
    file.family,
    file.format,
    file.report_month,
    file.baseline,
    team_type.showdown_id AS team_type,
    file.url,
    file.retrieved_at
FROM {{ source('raw', 'source_file') }} AS file
INNER JOIN ranked ON ranked.source_file_id = file.source_file_id AND ranked.version_rank = 1
LEFT JOIN {{ source('reference', 'type') }} AS team_type ON team_type.type_id = file.team_type_id
