-- Share of each Pokémon's teams that include each teammate, per report scope.
-- Shares sum to just under 5 per Pokémon (five other slots), since chaos leaves out teammates with negligible weight.
-- Unfilled team slots are left out; Smogon gives them no weight.
SELECT
    pokemon.format,
    pokemon.report_month,
    pokemon.baseline,
    pokemon.team_type,
    species.species_id,
    species.showdown_id AS species,
    species.name AS species_name,
    teammate.species_id AS teammate_species_id,
    teammate.showdown_id AS teammate_species,
    teammate.name AS teammate_species_name,
    TRIM_SCALE(ROUND((option.weight / pokemon.ability_weight_total)::NUMERIC, 10)) AS share,
    pokemon.source_file_id
FROM {{ ref('stg_chaos_teammate') }} AS option
INNER JOIN {{ ref('stg_chaos_pokemon') }} AS pokemon ON pokemon.chaos_pokemon_id = option.chaos_pokemon_id
INNER JOIN {{ source('reference', 'species') }} AS species ON species.species_id = pokemon.species_id
INNER JOIN {{ source('reference', 'species') }} AS teammate ON teammate.species_id = option.teammate_species_id
