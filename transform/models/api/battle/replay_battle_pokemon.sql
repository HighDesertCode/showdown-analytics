{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='replay_id', on_schema_change='fail') }}
-- Each Pokémon previewed in a parsed public replay. Incremental: a build adds every battle whose current parse
-- isn't in the table yet, replacing all rows of a re-parsed battle; a change to this model needs --full-refresh.
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
-- Checks each battle's own parse, so one committed out of timestamp order is still added.
WHERE NOT EXISTS (
    SELECT 1 FROM {{ this }} AS loaded
    WHERE loaded.replay_id = battle.replay_id AND loaded.parsed_at = battle.parsed_at
)
{% endif %}
