-- Share of each Pokémon's sets with each ability, per report scope. Shares sum to 1 per Pokémon.
-- Every chaos share uses the same denominator, the Pokémon's total ability weight, which matches Smogon's
-- moveset reports (e.g. overall 1630 Swampert: Earthquake 98.902%, Toxapex as a teammate 54.322%).
SELECT
    pokemon.format,
    pokemon.report_month,
    pokemon.baseline,
    pokemon.team_type,
    species.species_id,
    species.showdown_id AS species,
    species.name AS species_name,
    ability.ability_id,
    ability.showdown_id AS ability,
    ability.name AS ability_name,
    TRIM_SCALE(ROUND((option.weight / pokemon.ability_weight_total)::NUMERIC, 10)) AS share,
    pokemon.source_file_id
FROM {{ ref('stg_chaos_ability') }} AS option
INNER JOIN {{ ref('stg_chaos_pokemon') }} AS pokemon ON pokemon.chaos_pokemon_id = option.chaos_pokemon_id
INNER JOIN {{ source('reference', 'species') }} AS species ON species.species_id = pokemon.species_id
INNER JOIN {{ source('reference', 'ability') }} AS ability ON ability.ability_id = option.ability_id
