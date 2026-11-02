{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='replay_id', on_schema_change='fail') }}
-- Each game event in a parsed public replay, in log order, with the species of the form each Pokémon is in.
-- Incremental: a build adds every battle whose current parse isn't in the table yet, replacing all rows of a
-- re-parsed battle; a change to this model needs --full-refresh.
WITH battle AS (
    SELECT replay_id, parsed_at
    FROM {{ ref('stg_battle') }} AS battle
    {% if is_incremental() %}
    -- Checks each battle's own parse, so one committed out of timestamp order is still added.
    WHERE NOT EXISTS (
        SELECT 1 FROM {{ this }} AS loaded
        WHERE loaded.replay_id = battle.replay_id AND loaded.parsed_at = battle.parsed_at
    )
    {% endif %}
),

event AS (
    SELECT event.*, battle.parsed_at
    FROM {{ ref('stg_battle_event') }} AS event
    INNER JOIN battle ON battle.replay_id = event.replay_id
),

team AS (
    -- One row per previewed species: events name Pokémon by species, so a species previewed twice (which the
    -- parser rejects) must not multiply them.
    SELECT DISTINCT
        pokemon.replay_id,
        pokemon.side,
        pokemon.previewed_species,
        pokemon.species_id,
        COALESCE(species.base_species, species.name) AS base_species
    FROM {{ ref('stg_battle_pokemon') }} AS pokemon
    INNER JOIN battle ON battle.replay_id = pokemon.replay_id
    INNER JOIN {{ source('reference', 'species') }} AS species ON species.species_id = pokemon.species_id
),

form AS (
    -- Each time a Pokémon shows its form (switching in, being dragged in, an Illusion ending, or changing form),
    -- it holds until the next. A disguised Zoroark's switch-in shows the Pokémon it impersonates, so only forms of
    -- its own species count. A cosmetic form reference.species doesn't list matches its base species.
    SELECT
        event.replay_id,
        event.side,
        event.pokemon,
        event.seq AS from_seq,
        LEAD(event.seq) OVER (PARTITION BY event.replay_id, event.side, event.pokemon ORDER BY event.seq) AS to_seq,
        COALESCE(shown.species_id, shown_base.species_id) AS species_id
    FROM event
    INNER JOIN team
        ON team.replay_id = event.replay_id AND team.side = event.side AND team.previewed_species = event.pokemon
    LEFT JOIN {{ source('reference', 'species') }} AS shown ON shown.showdown_id = {{ to_id('event.detail') }}
    LEFT JOIN {{ source('reference', 'species') }} AS shown_base
        ON shown.species_id IS NULL
        AND shown_base.showdown_id = {{ to_id("SPLIT_PART(event.detail, '-', 1)") }}
    WHERE
        event.event IN ('switch', 'drag', 'replace', 'form')
        AND COALESCE(shown.base_species, shown.name, shown_base.base_species, shown_base.name) = team.base_species
)

SELECT
    event.replay_id,
    event.seq,
    event.turn,
    event.side,
    event.pokemon,
    -- Before a Pokémon shows a form (a Zoroark still disguised), its previewed species.
    COALESCE(pokemon_form.species_id, pokemon.species_id) AS species_id,
    event.event,
    event.detail,
    event.target_side,
    event.target_pokemon,
    COALESCE(target_form.species_id, target.species_id) AS target_species_id,
    event.damage_percent,
    event.hp_after_percent,
    event.healed_percent,
    event.caused_by_seq,
    event.source,
    event.source_inferred,
    event.parsed_at
FROM event
LEFT JOIN team AS pokemon
    ON pokemon.replay_id = event.replay_id
    AND pokemon.side = event.side
    AND pokemon.previewed_species = event.pokemon
LEFT JOIN form AS pokemon_form
    ON pokemon_form.replay_id = event.replay_id
    AND pokemon_form.side = event.side
    AND pokemon_form.pokemon = event.pokemon
    AND event.seq >= pokemon_form.from_seq
    AND (pokemon_form.to_seq IS NULL OR event.seq < pokemon_form.to_seq)
LEFT JOIN team AS target
    ON target.replay_id = event.replay_id
    AND target.side = event.target_side
    AND target.previewed_species = event.target_pokemon
LEFT JOIN form AS target_form
    ON target_form.replay_id = event.replay_id
    AND target_form.side = event.target_side
    AND target_form.pokemon = event.target_pokemon
    AND event.seq >= target_form.from_seq
    AND (target_form.to_seq IS NULL OR event.seq < target_form.to_seq)
