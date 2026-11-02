-- Sample sizes for the replay statistics: per month and Elo band, the rated teams in public replays and how many
-- have an inferred type. Battle counts cover the whole month, so each band's row repeats them.
WITH month_total AS (
    SELECT
        format,
        report_month,
        COUNT(*) AS battle_count,
        COUNT(*) FILTER (WHERE rated) AS rated_battle_count
    FROM {{ ref('replay_battle') }}
    GROUP BY format, report_month
)

SELECT
    battle.format,
    battle.report_month,
    side.elo_band,
    MIN(month_total.battle_count) AS battle_count,
    MIN(month_total.rated_battle_count) AS rated_battle_count,
    COUNT(*) AS team_count,
    COUNT(side.team_type) AS typed_team_count
FROM {{ ref('replay_battle_side') }} AS side
INNER JOIN {{ ref('replay_battle') }} AS battle ON battle.replay_id = side.replay_id
INNER JOIN month_total ON month_total.format = battle.format AND month_total.report_month = battle.report_month
WHERE battle.rated
GROUP BY battle.format, battle.report_month, side.elo_band
