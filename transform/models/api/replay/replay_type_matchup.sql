-- Rated battles, wins, and win rate for each team type against each opposing type, from public replays, by the
-- team's Elo band. win_rate is wins / battles, so ties lower it; mirror matches always split evenly, so their
-- win_rate is null. Teams without an inferred type are left out.
SELECT
    battle.format,
    battle.report_month,
    side.elo_band,
    team_type.type_id,
    team_type.showdown_id AS type,
    team_type.name AS type_name,
    opponent_type.type_id AS opponent_type_id,
    opponent_type.showdown_id AS opponent_type,
    opponent_type.name AS opponent_type_name,
    team_type.type_id = opponent_type.type_id AS is_mirror,
    COUNT(*) AS battle_count,
    COUNT(*) FILTER (WHERE side.result = 'win') AS win_count,
    COUNT(*) FILTER (WHERE side.result = 'tie') AS tie_count,
    CASE
        WHEN team_type.type_id <> opponent_type.type_id
            THEN TRIM_SCALE(ROUND(COUNT(*) FILTER (WHERE side.result = 'win')::NUMERIC / COUNT(*), 10))
    END AS win_rate
FROM {{ ref('replay_battle_side') }} AS side
INNER JOIN {{ ref('replay_battle_side') }} AS opponent
    ON opponent.replay_id = side.replay_id AND opponent.side <> side.side
INNER JOIN {{ ref('replay_battle') }} AS battle ON battle.replay_id = side.replay_id
INNER JOIN {{ source('reference', 'type') }} AS team_type ON team_type.type_id = side.team_type_id
INNER JOIN {{ source('reference', 'type') }} AS opponent_type ON opponent_type.type_id = opponent.team_type_id
WHERE battle.rated
GROUP BY
    battle.format,
    battle.report_month,
    side.elo_band,
    team_type.type_id,
    team_type.showdown_id,
    team_type.name,
    opponent_type.type_id,
    opponent_type.showdown_id,
    opponent_type.name
