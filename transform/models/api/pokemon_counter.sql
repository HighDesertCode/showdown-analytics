-- Checks and counters per Pokémon, from overall chaos reports only (per-type reports don't include them).
-- Rates are 0-to-1 proportions; Smogon's moveset reports show them as percentages,
-- e.g. overall 1630 Dragapult: Excadrill 55.049 (70.70±3.91).
SELECT
    pokemon.format,
    pokemon.report_month,
    pokemon.baseline,
    pokemon.team_type,
    species.species_id,
    species.showdown_id AS species,
    species.name AS species_name,
    opponent.species_id AS opponent_species_id,
    opponent.showdown_id AS opponent_species,
    opponent.name AS opponent_species_name,
    TRIM_SCALE(ROUND(counter.encounters::NUMERIC, 10)) AS encounters,
    TRIM_SCALE(ROUND(counter.ko_or_switch_rate::NUMERIC, 10)) AS ko_or_switch_rate,
    TRIM_SCALE(ROUND(counter.ko_or_switch_rate_std_dev::NUMERIC, 10)) AS ko_or_switch_rate_std_dev,
    TRIM_SCALE(ROUND(counter.score::NUMERIC, 10)) AS score,
    pokemon.source_file_id
FROM {{ ref('stg_chaos_counter') }} AS counter
INNER JOIN {{ ref('stg_chaos_pokemon') }} AS pokemon ON pokemon.chaos_pokemon_id = counter.chaos_pokemon_id
INNER JOIN {{ source('reference', 'species') }} AS species ON species.species_id = pokemon.species_id
INNER JOIN {{ source('reference', 'species') }} AS opponent ON opponent.species_id = counter.opponent_species_id
