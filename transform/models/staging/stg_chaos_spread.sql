-- Weighted EV spreads per Pokémon in each current chaos report. Smogon's label (e.g. "Timid:0/0/4/252/0/252")
-- is split into its nature, matched to reference.nature, and six EV values; the original label is kept.
WITH spreads AS (
    SELECT
        option.chaos_pokemon_id,
        option.label,
        option.weight,
        SPLIT_PART(option.label, ':', 1) AS nature_name,
        SPLIT_PART(option.label, ':', 2) AS evs
    FROM {{ source('raw', 'chaos_option') }} AS option
    INNER JOIN {{ ref('stg_chaos_pokemon') }} AS pokemon ON pokemon.chaos_pokemon_id = option.chaos_pokemon_id
    WHERE option.category = 'spreads'
)

SELECT
    spreads.chaos_pokemon_id,
    nature.nature_id,
    spreads.label,
    SPLIT_PART(spreads.evs, '/', 1)::SMALLINT AS hp_evs,
    SPLIT_PART(spreads.evs, '/', 2)::SMALLINT AS atk_evs,
    SPLIT_PART(spreads.evs, '/', 3)::SMALLINT AS def_evs,
    SPLIT_PART(spreads.evs, '/', 4)::SMALLINT AS spa_evs,
    SPLIT_PART(spreads.evs, '/', 5)::SMALLINT AS spd_evs,
    SPLIT_PART(spreads.evs, '/', 6)::SMALLINT AS spe_evs,
    spreads.weight
FROM spreads
LEFT JOIN {{ source('reference', 'nature') }} AS nature ON nature.showdown_id = {{ to_id('spreads.nature_name') }}
