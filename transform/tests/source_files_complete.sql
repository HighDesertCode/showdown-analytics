-- Every loaded month and baseline has all 77 current files: the overall report and 18 per-type reports for
-- each of four families, plus one matchup chart. Returns each family that has a different count.
WITH expected AS (
    SELECT family, file_count
    FROM (
        VALUES
            ('chaos', 19),
            ('usage', 19),
            ('leads', 19),
            ('metagame', 19),
            ('matchup_chart', 1)
    ) AS expected (family, file_count)
),

loaded AS (
    SELECT DISTINCT format, report_month, baseline
    FROM {{ ref('stg_source_file') }}
),

actual AS (
    SELECT format, report_month, baseline, family, COUNT(*) AS file_count
    FROM {{ ref('stg_source_file') }}
    GROUP BY format, report_month, baseline, family
)

SELECT
    loaded.format,
    loaded.report_month,
    loaded.baseline,
    expected.family,
    expected.file_count AS expected_file_count,
    COALESCE(actual.file_count, 0) AS actual_file_count
FROM loaded
CROSS JOIN expected
LEFT JOIN actual
    ON actual.format = loaded.format
    AND actual.report_month = loaded.report_month
    AND actual.baseline = loaded.baseline
    AND actual.family = expected.family
WHERE COALESCE(actual.file_count, 0) <> expected.file_count
