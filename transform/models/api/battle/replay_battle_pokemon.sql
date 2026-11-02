{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='replay_id', on_schema_change='fail') }}
-- Each Pokémon previewed in a parsed public replay. Incremental: a build adds only battles parsed since the last
-- one, replacing every row of a re-parsed battle; a change to this model needs --full-refresh.
SELECT
    pokemon.replay_id,
    pokemon.side,
    pokemon.slot,
    pokemon.previewed_species,
    pokemon.species_id,
    pokemon.form_hidden,
    pokemon.nickname,
    battle.parsed_at
FROM {{ ref('stg_battle_pokemon') }} AS pokemon
INNER JOIN {{ ref('stg_battle') }} AS battle ON battle.replay_id = pokemon.replay_id
{% if is_incremental() %}
-- An empty table has no latest parse, so every battle is new.
WHERE battle.parsed_at > (SELECT COALESCE(MAX(parsed_at), '-infinity') FROM {{ this }})
{% endif %}
