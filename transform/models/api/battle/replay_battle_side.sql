{{ config(indexes=[{'columns': ['player_id']}]) }}
-- Each player in a parsed public replay, with their Elo band and their team's inferred type. The index serves the
-- API's battle search by player. player_id is Showdown's user ID for the name: lowercase letters and digits only.
SELECT
    replay_id,
    side,
    player,
    {{ to_id('player') }} AS player_id,
    elo_before,
    elo_after,
    elo_band,
    result,
    team_type_id,
    team_type
FROM {{ ref('stg_battle_side') }}
