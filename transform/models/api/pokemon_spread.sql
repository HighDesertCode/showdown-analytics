-- Share of each Pokémon's sets with each nature and EV spread, per report scope. Shares sum to 1 per Pokémon.
-- spread keeps Smogon's label (e.g. Timid:0/0/4/252/0/252).
SELECT
    pokemon.format,
    pokemon.report_month,
    pokemon.baseline,
    pokemon.team_type,
    species.species_id,
    species.showdown_id AS species,
    species.name AS species_name,
    option.label AS spread,
    nature.nature_id,
    nature.showdown_id AS nature,
    nature.name AS nature_name,
    option.hp_evs,
    option.atk_evs,
    option.def_evs,
    option.spa_evs,
    option.spd_evs,
    option.spe_evs,
    TRIM_SCALE(ROUND((option.weight / pokemon.ability_weight_total)::NUMERIC, 10)) AS share,
    pokemon.source_file_id
FROM {{ ref('stg_chaos_spread') }} AS option
INNER JOIN {{ ref('stg_chaos_pokemon') }} AS pokemon ON pokemon.chaos_pokemon_id = option.chaos_pokemon_id
INNER JOIN {{ source('reference', 'species') }} AS species ON species.species_id = pokemon.species_id
INNER JOIN {{ source('reference', 'nature') }} AS nature ON nature.nature_id = option.nature_id
