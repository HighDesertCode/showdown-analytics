-- One row per Smogon file behind the api tables (the latest version of each URL).
-- Every api statistic links here through its source_file_id column(s).
SELECT
    file.source_file_id,
    file.family,
    file.format,
    file.report_month,
    file.baseline,
    file.team_type,
    file.url,
    file.content_sha256,
    file.byte_size,
    file.retrieved_at
FROM {{ ref('stg_source_file') }} AS file
