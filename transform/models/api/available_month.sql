-- One row per month and baseline in the api tables, so clients can find the latest month and list the others.
-- The staging tests fail the build unless every loaded month has all 77 files, so every month here is complete.
SELECT
    format,
    report_month,
    baseline,
    COUNT(*)::INTEGER AS file_count,
    MAX(retrieved_at) AS last_retrieved_at
FROM {{ ref('stg_source_file') }}
GROUP BY format, report_month, baseline
