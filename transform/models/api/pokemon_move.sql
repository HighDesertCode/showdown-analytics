-- Share of each Pokémon's sets with each move, per report scope. Shares sum to at most 4 per Pokémon (four move slots).
-- Unused move slots are left out: Smogon counts each one, so a one-move set adds 3 and the value isn't a share.
SELECT
    pokemon.format,
    pokemon.report_month,
    pokemon.baseline,
    pokemon.team_type,
    species.species_id,
    species.showdown_id AS species,
    species.name AS species_name,
    move.move_id,
    move.showdown_id AS move,
    move.name AS move_name,
    TRIM_SCALE(ROUND((option.weight / pokemon.ability_weight_total)::NUMERIC, 10)) AS share,
    pokemon.source_file_id
FROM {{ ref('stg_chaos_move') }} AS option
INNER JOIN {{ ref('stg_chaos_pokemon') }} AS pokemon ON pokemon.chaos_pokemon_id = option.chaos_pokemon_id
INNER JOIN {{ source('reference', 'species') }} AS species ON species.species_id = pokemon.species_id
INNER JOIN {{ source('reference', 'move') }} AS move ON move.move_id = option.move_id
