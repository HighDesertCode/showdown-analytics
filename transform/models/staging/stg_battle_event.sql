-- One row per game event, without the log line. pokemon and target_pokemon are the species shown at team preview,
-- so they join to stg_battle_pokemon; replay_battle_event works out the form each one is in.
SELECT
    replay_id,
    seq,
    turn,
    side,
    pokemon,
    event,
    detail,
    target_side,
    target_pokemon,
    damage_percent,
    hp_after_percent,
    healed_percent,
    caused_by_seq,
    source,
    source_inferred
FROM {{ source('raw', 'battle_event') }}
