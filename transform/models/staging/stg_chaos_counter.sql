-- Checks and counters per Pokémon in each current overall chaos report, matched to reference.species.
-- Smogon's n, p, and d: weighted encounters, the share of encounters where the Pokémon was KOed or forced
-- to switch out by the opponent, and that share's standard deviation. Smogon ranks counters by p - 4d.
SELECT
    counter.chaos_pokemon_id,
    species.species_id AS opponent_species_id,
    counter.opponent AS opponent_name,
    counter.n AS encounters,
    counter.p AS ko_or_switch_rate,
    counter.d AS ko_or_switch_rate_std_dev,
    counter.p - 4 * counter.d AS score
FROM {{ source('raw', 'chaos_counter') }} AS counter
INNER JOIN {{ ref('stg_chaos_pokemon') }} AS pokemon ON pokemon.chaos_pokemon_id = counter.chaos_pokemon_id
LEFT JOIN {{ source('reference', 'species') }} AS species ON species.showdown_id = {{ to_id('counter.opponent') }}
