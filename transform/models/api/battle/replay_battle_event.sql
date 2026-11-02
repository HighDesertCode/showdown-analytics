{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='replay_id', on_schema_change='fail') }}
-- Each game event in a parsed public replay, in log order. Incremental: a build adds only battles parsed since
-- the last one, replacing every row of a re-parsed battle; a change to this model needs --full-refresh.
SELECT
    event.replay_id,
    event.seq,
    event.turn,
    event.side,
    event.pokemon,
    event.species_id,
    event.event,
    event.detail,
    event.target_side,
    event.target_pokemon,
    event.target_species_id,
    event.damage_percent,
    event.hp_after_percent,
    event.healed_percent,
    event.caused_by_seq,
    event.source,
    event.source_inferred,
    battle.parsed_at
FROM {{ ref('stg_battle_event') }} AS event
INNER JOIN {{ ref('stg_battle') }} AS battle ON battle.replay_id = event.replay_id
{% if is_incremental() %}
-- An empty table has no latest parse, so every battle is new.
WHERE battle.parsed_at > (SELECT COALESCE(MAX(parsed_at), '-infinity') FROM {{ this }})
{% endif %}
