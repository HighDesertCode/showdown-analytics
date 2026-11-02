-- One row per parsed public replay: a sample of the battles players chose to upload, not the whole ladder.
SELECT
    replay_id,
    format,
    report_month,
    replay_url,
    rated,
    started_at,
    ended_at,
    turns,
    winner,
    ended_by,
    rules,
    uploaded_at,
    parsed_at
FROM {{ ref('stg_battle') }}
