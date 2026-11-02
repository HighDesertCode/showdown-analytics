-- One row per parsed replay, with its format, the UTC month it started in, and its public replay page.
SELECT
    battle.replay_id,
    replay.format_id AS format,
    DATE_TRUNC('month', battle.started_at AT TIME ZONE 'UTC')::DATE AS report_month,
    'https://replay.pokemonshowdown.com/' || battle.replay_id AS replay_url,
    battle.rated,
    battle.started_at,
    battle.ended_at,
    battle.turns,
    battle.winner,
    battle.ended_by,
    battle.rules,
    replay.uploaded_at
FROM {{ source('raw', 'battle') }} AS battle
INNER JOIN {{ source('raw', 'replay') }} AS replay ON replay.replay_id = battle.replay_id
