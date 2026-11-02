-- Each player in a parsed battle, with their Elo band and their team's type. Elo is Showdown's ladder rating,
-- never comparable to Smogon's Glicko-weighted baselines. The team type isn't in the log: it is inferred as
-- the one type every previewed Pokémon shares, and is null when they share none or more than one.
WITH pokemon_type AS (
    -- A hidden form could be any form of its species, so it counts as having every type they have.
    SELECT DISTINCT
        pokemon.replay_id,
        pokemon.side,
        pokemon.slot,
        form_type.type_id
    FROM {{ ref('stg_battle_pokemon') }} AS pokemon
    INNER JOIN {{ source('reference', 'species') }} AS species ON species.species_id = pokemon.species_id
    INNER JOIN {{ source('reference', 'species') }} AS form
        ON form.species_id = species.species_id
        OR (pokemon.form_hidden AND form.base_species = species.name)
    CROSS JOIN LATERAL (VALUES (form.type_1_id), (form.type_2_id)) AS form_type (type_id)
    WHERE form_type.type_id IS NOT NULL
),

team_size AS (
    SELECT replay_id, side, COUNT(*) AS pokemon_count
    FROM {{ ref('stg_battle_pokemon') }}
    GROUP BY replay_id, side
),

shared_type AS (
    SELECT pokemon_type.replay_id, pokemon_type.side, pokemon_type.type_id
    FROM pokemon_type
    INNER JOIN team_size ON team_size.replay_id = pokemon_type.replay_id AND team_size.side = pokemon_type.side
    GROUP BY pokemon_type.replay_id, pokemon_type.side, pokemon_type.type_id, team_size.pokemon_count
    HAVING COUNT(*) = team_size.pokemon_count
),

team_type AS (
    SELECT replay_id, side, MIN(type_id) AS type_id
    FROM shared_type
    GROUP BY replay_id, side
    HAVING COUNT(*) = 1
)

SELECT
    side.replay_id,
    side.side,
    side.player,
    side.elo_before,
    side.elo_after,
    -- The lower bound of the player's Elo before the battle; 1000 is the ladder's floor. Null when unrated.
    CASE
        WHEN side.elo_before < 1200 THEN 1000
        WHEN side.elo_before < 1400 THEN 1200
        WHEN side.elo_before < 1600 THEN 1400
        WHEN side.elo_before >= 1600 THEN 1600
    END AS elo_band,
    side.result,
    team_type.type_id AS team_type_id,
    type.showdown_id AS team_type
FROM {{ source('raw', 'battle_side') }} AS side
LEFT JOIN team_type ON team_type.replay_id = side.replay_id AND team_type.side = side.side
LEFT JOIN {{ source('reference', 'type') }} AS type ON type.type_id = team_type.type_id
