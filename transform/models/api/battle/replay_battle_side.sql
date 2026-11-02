-- Each player in a parsed public replay, with their Elo band and their team's inferred type.
SELECT
    replay_id,
    side,
    player,
    elo_before,
    elo_after,
    elo_band,
    result,
    team_type_id,
    team_type
FROM {{ ref('stg_battle_side') }}
